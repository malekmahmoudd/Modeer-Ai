"""What the team keeps track of between conversations.

* Follow-ups — dated things the person mentioned ("interview on Thu 1 Oct").
  They count down in the briefing and in the owning agent's context. Once the
  day has passed, that agent (and Leo) is prompted to ask how it went, once.
* Check-ins — progress the person reported ("ran 5k", "spent 40 on food"),
  shown to the agent it belongs with as the last two weeks' log.
* Saved plans — see ``plans.py``.
* The weekly review — built from the above with no model call.

All of it is captured by the turn analysis, which already runs, or by explicit
requests. Nothing here costs an extra provider call.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.text import as_data
from app.db.models import CheckIn, FollowUp, Goal, Plan, PlanStep
from app.tracking import plans as plan_service

UPCOMING_DAYS = 30
#: The same title this close in time is the same event mentioned again.
SAME_EVENT_DAYS = 3
#: The briefing asks "How did it go?" only this soon after, and only until an
#: agent has asked in chat: once, not every morning for two weeks.
ASK_IN_BRIEFING_DAYS = 3
ASK_WITHIN_DAYS = 14
CHECKIN_DAYS = 14
MAX_CONTEXT_LINES = 10


def _day(d: date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


def countdown(due: date, today: date) -> str:
    days = (due - today).days
    if days == 0:
        return f"today ({_day(due)})"
    if days == 1:
        return f"tomorrow ({_day(due)})"
    if days < 0:
        return f"{_day(due)}, {-days} day{'s' if days != -1 else ''} ago"
    return f"{_day(due)} (in {days} days)"


# --- follow-ups -------------------------------------------------------------------


def add_followup(
    db: Session,
    user_id: str,
    *,
    agent_id: str,
    title: str,
    due_on: date,
    source_message_id: str | None = None,
) -> tuple[FollowUp, bool]:
    """The follow-up, and whether it is new.

    The same title within a few days is the same event mentioned again ("the
    interview is actually Friday" moves it). The same title weeks apart is a
    second event — a dentist appointment every six months is not one follow-up.
    """
    existing = db.scalar(
        select(FollowUp).where(
            FollowUp.user_id == user_id,
            FollowUp.status == "pending",
            func.lower(FollowUp.title) == title.lower(),
            FollowUp.due_on >= due_on - timedelta(days=SAME_EVENT_DAYS),
            FollowUp.due_on <= due_on + timedelta(days=SAME_EVENT_DAYS),
        )
    )
    if existing is not None:
        if existing.due_on != due_on:
            existing.due_on, existing.asked_at = due_on, None
            db.flush()
            return existing, True
        return existing, False
    row = FollowUp(
        user_id=user_id,
        agent_id=agent_id,
        title=title,
        due_on=due_on,
        source_message_id=source_message_id,
    )
    db.add(row)
    db.flush()
    return row, True


def list_followups(db: Session, user_id: str, *, status: str | None = None) -> list[FollowUp]:
    stmt = select(FollowUp).where(FollowUp.user_id == user_id)
    if status:
        stmt = stmt.where(FollowUp.status == status)
    return list(db.scalars(stmt.order_by(FollowUp.due_on)))


def get_followup(db: Session, user_id: str, followup_id: str) -> FollowUp | None:
    return db.scalar(
        select(FollowUp).where(FollowUp.id == followup_id, FollowUp.user_id == user_id)
    )


def expire_followups(db: Session, user_id: str, *, today: date) -> None:
    """Close follow-ups nobody answered about within two weeks of the day, so
    the pending list and the calendar export do not grow forever."""
    for row in db.scalars(
        select(FollowUp).where(
            FollowUp.user_id == user_id,
            FollowUp.status == "pending",
            FollowUp.due_on < today - timedelta(days=ASK_WITHIN_DAYS),
        )
    ):
        row.status = "dismissed"
    db.flush()


def awaiting_answer(
    db: Session, user_id: str, *, agent_id: str, is_leo: bool, today: date
) -> list[FollowUp]:
    """Passed follow-ups the team has asked about and not yet heard back on."""
    return [
        f
        for f in list_followups(db, user_id, status="pending")
        if f.asked_at is not None and f.due_on < today and (is_leo or f.agent_id == agent_id)
    ][:3]


def close_followups(db: Session, user_id: str, outcomes: list) -> list[FollowUp]:
    """Mark answered follow-ups done, keeping how it went in the user's words."""
    closed: list[FollowUp] = []
    for item in outcomes:
        row = get_followup(db, user_id, item.followup_id)
        if row is None or row.status != "pending":
            continue
        row.status, row.outcome = "done", item.outcome
        closed.append(row)
    db.flush()
    return closed


def _ask_in_briefing(row, today: date) -> bool:
    return (
        row.asked_at is None and today - timedelta(days=ASK_IN_BRIEFING_DAYS) <= row.due_on < today
    )


def mark_asked(db: Session, ids: list[str]) -> None:
    if not ids:
        return
    now = datetime.now(UTC)
    for row in db.scalars(select(FollowUp).where(FollowUp.id.in_(ids))):
        row.asked_at = row.asked_at or now
    db.flush()


# --- check-ins -----------------------------------------------------------------------


def add_checkin(
    db: Session,
    user_id: str,
    *,
    agent_id: str,
    text: str,
    amount: float | None,
    unit: str | None,
    logged_on: date,
    source_message_id: str | None = None,
) -> CheckIn:
    row = CheckIn(
        user_id=user_id,
        agent_id=agent_id,
        text=text,
        amount=amount,
        unit=unit,
        logged_on=logged_on,
        source_message_id=source_message_id,
    )
    db.add(row)
    db.flush()
    return row


def list_checkins(
    db: Session, user_id: str, *, agent_id: str | None = None, since: date | None = None
) -> list[CheckIn]:
    stmt = select(CheckIn).where(CheckIn.user_id == user_id)
    if agent_id:
        stmt = stmt.where(CheckIn.agent_id == agent_id)
    if since:
        stmt = stmt.where(CheckIn.logged_on >= since)
    return list(db.scalars(stmt.order_by(CheckIn.logged_on.desc(), CheckIn.created_at.desc())))


def _checkin_line(row: CheckIn) -> str:
    amount = ""
    if row.amount is not None:
        figure = f"{row.amount:g}"
        amount = f" ({figure}{' ' + row.unit if row.unit else ''})"
    return f"{_day(row.logged_on)}: {as_data(row.text)}{amount}"


# --- what an agent is told ------------------------------------------------------------


def context_sections(
    db: Session, user_id: str, *, agent_id: str, is_leo: bool, today: date
) -> tuple[list[str], list[str]]:
    """Rendered sections for this agent's prompt, and the follow-ups it is now
    prompted to ask about (mark them asked once the reply is delivered)."""

    def mine(row) -> bool:
        return is_leo or row.agent_id == agent_id

    expire_followups(db, user_id, today=today)
    pending = [f for f in list_followups(db, user_id, status="pending") if mine(f)]
    upcoming = [f for f in pending if today <= f.due_on <= today + timedelta(days=UPCOMING_DAYS)][
        :MAX_CONTEXT_LINES
    ]
    to_ask = [
        f
        for f in pending
        if today - timedelta(days=ASK_WITHIN_DAYS) <= f.due_on < today and f.asked_at is None
    ][:3]
    active = [p for p in plan_service.list_plans(db, user_id, status="active") if mine(p)][:3]
    logged = (
        list_checkins(db, user_id, agent_id=agent_id, since=today - timedelta(days=CHECKIN_DAYS))[
            :MAX_CONTEXT_LINES
        ]
        if not is_leo
        else []
    )

    sections: list[str] = []
    if upcoming:
        sections.append(
            "## Coming up (dates the user gave; you may count down to them)\n"
            + "\n".join(f"- {as_data(f.title)} — {countdown(f.due_on, today)}" for f in upcoming)
        )
    if to_ask:
        sections.append(
            "## Recently passed — ask how it went, once and briefly, if it fits this turn\n"
            + "\n".join(f"- {as_data(f.title)} — {countdown(f.due_on, today)}" for f in to_ask)
        )
    if active:
        sections.append(
            "## Plans the user saved (checklists they are working through)\n"
            + "\n".join(f"- {as_data(plan_service.progress_line(p, today))}" for p in active)
        )
    if logged:
        sections.append(
            f"## Progress they logged with you (last {CHECKIN_DAYS} days, newest first)\n"
            + "\n".join(f"- {_checkin_line(c)}" for c in logged)
        )
    return sections, [f.id for f in to_ask]


# --- briefing and weekly review ---------------------------------------------------------


def briefing_items(db: Session, user_id: str, *, today: date) -> list[dict]:
    """Follow-ups and plan steps worth a line in today's briefing."""
    items: list[dict] = []
    expire_followups(db, user_id, today=today)
    pending = list_followups(db, user_id, status="pending")
    for f in pending:
        if _ask_in_briefing(f, today):
            items.append(
                {
                    "icon": "💬",
                    "text": f"How did it go? {f.title}",
                    "detail": countdown(f.due_on, today),
                    "source": "followup",
                    "agent": f.agent_id,
                }
            )
    for f in pending:
        if today <= f.due_on <= today + timedelta(days=7):
            items.append(
                {
                    "icon": "📅",
                    "text": f.title,
                    "detail": countdown(f.due_on, today).capitalize(),
                    "source": "followup",
                    "agent": f.agent_id,
                }
            )
    for plan in plan_service.list_plans(db, user_id, status="active"):
        step = next((s for s in plan.steps if s.done_at is None), None)
        if step is not None and step.due_on is not None and step.due_on <= today:
            items.append(
                {
                    "icon": "✅",
                    "text": step.text[:160],
                    "detail": f"{plan.title} — "
                    + ("due today" if step.due_on == today else "overdue"),
                    "source": "plan",
                    "agent": plan.agent_id,
                }
            )
    return items[:6]


def weekly_review(db: Session, user_id: str, *, today: date) -> dict:
    """The last seven days and the next seven, from what is stored. No model call."""
    start = today - timedelta(days=7)
    week_start = datetime.combine(start, datetime.min.time(), tzinfo=UTC)

    steps_done = list(
        db.scalars(
            select(PlanStep)
            .join(Plan)
            .where(Plan.user_id == user_id, PlanStep.done_at.is_not(None))
        )
    )
    steps_done = [s for s in steps_done if _aware(s.done_at) >= week_start]
    checkins = list_checkins(db, user_id, since=start)
    passed = [
        f
        for f in list_followups(db, user_id)
        if start <= f.due_on < today and f.status != "dismissed"
    ]
    goals_done = [
        g
        for g in db.scalars(select(Goal).where(Goal.user_id == user_id, Goal.status == "done"))
        if g.updated_at and _aware(g.updated_at) >= week_start
    ]
    coming = [
        f
        for f in list_followups(db, user_id, status="pending")
        if today <= f.due_on <= today + timedelta(days=7)
    ]
    due_steps = [
        (p, s)
        for p in plan_service.list_plans(db, user_id, status="active")
        for s in p.steps
        if s.done_at is None and s.due_on and today <= s.due_on <= today + timedelta(days=7)
    ]

    by_agent: dict[str, int] = {}
    for c in checkins:
        by_agent[c.agent_id] = by_agent.get(c.agent_id, 0) + 1

    last: list[str] = []
    if steps_done:
        last.append(f"{len(steps_done)} plan step{'s' if len(steps_done) != 1 else ''} done")
    if checkins:
        last.append(f"{len(checkins)} check-in{'s' if len(checkins) != 1 else ''} logged")
    if goals_done:
        last.append("goal completed: " + ", ".join(g.title for g in goals_done[:3]))
    if passed:
        last.append("behind you: " + ", ".join(f.title for f in passed[:3]))
    nxt: list[str] = [f"{f.title} {countdown(f.due_on, today)}" for f in coming[:3]]
    if due_steps:
        nxt.append(f"{len(due_steps)} plan step{'s' if len(due_steps) != 1 else ''} due")

    if last or nxt:
        summary = ("Last 7 days: " + "; ".join(last) + ". " if last else "A quiet week. ") + (
            "Next 7 days: " + "; ".join(nxt) + "." if nxt else "Nothing dated ahead yet."
        )
    else:
        summary = (
            "Nothing tracked yet. Save a plan, mention a date, or tell a teammate what "
            "you did, and your week shows up here."
        )
    return {
        "from": start.isoformat(),
        "to": today.isoformat(),
        "summary": summary,
        "plan_steps_done": len(steps_done),
        "checkins": by_agent,
        "goals_done": [g.title for g in goals_done],
        "followups_passed": [f.title for f in passed],
        "coming_up": [
            {"title": f.title, "due_on": f.due_on.isoformat(), "agent": f.agent_id} for f in coming
        ],
        "plan_steps_due": len(due_steps),
    }


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


# --- calendar export ------------------------------------------------------------------


def _ics_text(value: str) -> str:
    """Escaped for a TEXT property. A bare CR or LF would start a new property,
    so every line break becomes an escaped one."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines of at most 75 octets, continued with CRLF and a space.
    Never splits a UTF-8 character."""
    out, current = [], ""
    for ch in line:
        limit = 75 if not out else 74  # a continuation line starts with a space
        if len((current + ch).encode("utf-8")) > limit:
            out.append(current)
            current = ch
        else:
            current += ch
    out.append(current)
    return "\r\n ".join(out)


def to_ics(events: list[tuple[str, date, str]], *, name: str) -> str:
    """An iCalendar file of all-day events: (uid, day, summary)."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CrewAi//Personal AI Team//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_ics_text(name)}",
    ]
    for uid, day, summary in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@crewai",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_ics_text(summary[:200])}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
