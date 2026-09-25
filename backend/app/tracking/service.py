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

import re
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


def over_on(row) -> date:
    """The day a follow-up is over: its last day for a trip, else its day."""
    return getattr(row, "ends_on", None) or row.due_on


def when_line(row, today: date) -> str:
    """The countdown, or for a span "Tue 10 Nov → Sat 14 Nov (in 46 days)"."""
    ends = getattr(row, "ends_on", None)
    if not ends or ends == row.due_on:
        return countdown(row.due_on, today)
    span = f"{_day(row.due_on)} → {_day(ends)}"
    if today < row.due_on:
        days = (row.due_on - today).days
        return f"{span} ({'tomorrow' if days == 1 else f'in {days} days'})"
    if today <= ends:
        return f"{span} (happening now)"
    return f"{span}, ended {countdown(ends, today).split(', ', 1)[-1]}"


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
    ends_on: date | None = None,
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
        if existing.due_on != due_on or (ends_on and existing.ends_on != ends_on):
            existing.due_on, existing.asked_at = due_on, None
            existing.ends_on = ends_on or existing.ends_on
            db.flush()
            return existing, True
        return existing, False
    row = FollowUp(
        user_id=user_id,
        agent_id=agent_id,
        title=title,
        due_on=due_on,
        ends_on=ends_on,
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
    """Close follow-ups nobody answered about within two weeks of them ending,
    so the pending list and the calendar export do not grow forever."""
    for row in db.scalars(
        select(FollowUp).where(FollowUp.user_id == user_id, FollowUp.status == "pending")
    ):
        if over_on(row) < today - timedelta(days=ASK_WITHIN_DAYS):
            row.status = "dismissed"
    db.flush()


def awaiting_answer(
    db: Session, user_id: str, *, agent_id: str, is_leo: bool, today: date
) -> list[FollowUp]:
    """Passed follow-ups the team has asked about and not yet heard back on."""
    return [
        f
        for f in list_followups(db, user_id, status="pending")
        if f.asked_at is not None and over_on(f) < today and (is_leo or f.agent_id == agent_id)
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
        row.asked_at is None
        and today - timedelta(days=ASK_IN_BRIEFING_DAYS) <= over_on(row) < today
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
    details: dict | None = None,
    source_message_id: str | None = None,
) -> CheckIn:
    row = CheckIn(
        user_id=user_id,
        agent_id=agent_id,
        text=text,
        amount=amount,
        unit=unit,
        details=details,
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
    detail = _detail_text(row)
    if detail:
        return f"{_day(row.logged_on)}: {as_data(row.text)} ({detail})"
    amount = ""
    if row.amount is not None:
        figure = f"{row.amount:g}"
        amount = f" ({figure}{' ' + row.unit if row.unit else ''})"
    return f"{_day(row.logged_on)}: {as_data(row.text)}{amount}"


def _detail_text(row: CheckIn) -> str:
    """ "3×5 @ 80 kg, RPE 8" / "5 km in 28 min" / "spent 40 EGP", from the details."""
    d = row.details or {}
    parts: list[str] = []
    if d.get("sets") and d.get("reps"):
        parts.append(f"{d['sets']:g}×{d['reps']:g}")
    if d.get("load") is not None:
        parts.append(f"@ {d['load']:g} {as_data(d.get('load_unit', ''))}".rstrip())
    if d.get("rpe"):
        parts.append(f"RPE {d['rpe']:g}")
    if d.get("distance_km"):
        parts.append(f"{d['distance_km']:g} km")
    if d.get("duration_min"):
        parts.append(f"in {d['duration_min']:g} min")
    if d.get("direction") and row.amount is not None:
        verb = "spent" if d["direction"] == "out" else "received"
        currency = f" {as_data(d['currency'])}" if d.get("currency") else ""
        parts.append(f"{verb} {row.amount:g}{currency}")
    return " ".join(parts)


#: Weeks of workout logs Maddie sees summarised per exercise, for progression.
PROGRESSION_DAYS = 84


def progression_lines(db: Session, user_id: str, *, agent_id: str, today: date) -> list[str]:
    """Per exercise: the last session and the best load, from structured logs."""
    rows = list_checkins(
        db, user_id, agent_id=agent_id, since=today - timedelta(days=PROGRESSION_DAYS)
    )
    by_exercise: dict[str, list[CheckIn]] = {}
    for row in rows:  # newest first
        name = ((row.details or {}).get("exercise") or "").strip().lower()
        if name:
            by_exercise.setdefault(name, []).append(row)
    lines = []
    for name, logs in list(by_exercise.items())[:8]:
        last = logs[0]
        loads = [
            (r.details or {}).get("load") for r in logs if (r.details or {}).get("load") is not None
        ]
        best = (
            f"; best {max(loads):g} {as_data((last.details or {}).get('load_unit', ''))}"
            if loads
            else ""
        )
        lines.append(
            f"{as_data(name)}: last {_day(last.logged_on)} {_detail_text(last)}{best.rstrip()}"
            f" ({len(logs)} sessions)"
        )
    return lines


# --- what an agent is told ------------------------------------------------------------


def context_sections(
    db: Session, user_id: str, *, agent_id: str, is_leo: bool, today: date, message: str = ""
) -> tuple[list[str], list[str]]:
    """Rendered sections for this agent's prompt, and the follow-ups it is now
    prompted to ask about (mark them asked once the reply is delivered)."""

    def mine(row) -> bool:
        return is_leo or row.agent_id == agent_id

    expire_followups(db, user_id, today=today)
    pending = [f for f in list_followups(db, user_id, status="pending") if mine(f)]
    # Coming up, or under way (a trip that has started and not yet ended).
    upcoming = [
        f
        for f in pending
        if today <= over_on(f) and f.due_on <= today + timedelta(days=UPCOMING_DAYS)
    ][:MAX_CONTEXT_LINES]
    to_ask = [
        f
        for f in pending
        if today - timedelta(days=ASK_WITHIN_DAYS) <= over_on(f) < today and f.asked_at is None
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
            + "\n".join(f"- {as_data(f.title)} — {when_line(f, today)}" for f in upcoming)
        )
    if to_ask:
        sections.append(
            "## Recently passed — ask how it went, once and briefly, if it fits this turn\n"
            + "\n".join(f"- {as_data(f.title)} — {when_line(f, today)}" for f in to_ask)
        )
    if active:
        sections.append(
            "## Plans the user saved (checklists they are working through)\n"
            + "\n".join(f"- {as_data(plan_service.progress_line(p, today))}" for p in active)
        )
    progression = (
        progression_lines(db, user_id, agent_id=agent_id, today=today) if not is_leo else []
    )
    if progression:
        sections.append(
            f"## Progression from their logs (last {PROGRESSION_DAYS // 7} weeks) — base the "
            "next load or volume on these, not on guesses\n"
            + "\n".join(f"- {line}" for line in progression)
        )
    if logged:
        sections.append(
            f"## Progress they logged with you (last {CHECKIN_DAYS} days, newest first)\n"
            + "\n".join(f"- {_checkin_line(c)}" for c in logged)
        )
    if is_leo:
        review = review_section(db, user_id, today=today, message=message)
        if review:
            sections.append(review)
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
                    "detail": when_line(f, today),
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
                    "detail": when_line(f, today)[:1].upper() + when_line(f, today)[1:],
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
        if start <= over_on(f) < today and f.status != "dismissed"
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
    # Money out, added up in code (never by the model), per currency as given.
    spending: dict[str, float] = {}
    for c in checkins:
        detail = c.details or {}
        if detail.get("direction") == "out" and c.amount is not None:
            key = detail.get("currency") or "no currency given"
            spending[key] = round(spending.get(key, 0.0) + c.amount, 2)
    # Goals nobody has moved in a while: what a chief of staff would flag.
    quiet_goals = [
        g.title
        for g in db.scalars(select(Goal).where(Goal.user_id == user_id, Goal.status == "active"))
        if g.updated_at and _aware(g.updated_at) < week_start - timedelta(days=7)
    ][:3]

    last: list[str] = []
    if steps_done:
        last.append(f"{len(steps_done)} plan step{'s' if len(steps_done) != 1 else ''} done")
    if checkins:
        last.append(f"{len(checkins)} check-in{'s' if len(checkins) != 1 else ''} logged")
    if goals_done:
        last.append("goal completed: " + ", ".join(g.title for g in goals_done[:3]))
    if passed:
        last.append("behind you: " + ", ".join(f.title for f in passed[:3]))
    if spending:
        last.append(
            "spent "
            + ", ".join(
                f"{_money(total)} ({cur})" if cur.startswith("no ") else f"{_money(total)} {cur}"
                for cur, total in spending.items()
            )
        )
    nxt: list[str] = [f"{f.title} {countdown(f.due_on, today)}" for f in coming[:3]]
    if quiet_goals:
        nxt.append("no movement lately on: " + ", ".join(quiet_goals))
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
        "spending": spending,
        "quiet_goals": quiet_goals,
    }


def _money(value: float) -> str:
    return f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"


#: Asking Leo about the week, priorities or progress: he gets the week's data.
_REVIEW_ASK = re.compile(
    r"\b(week|weekly|review|recap|focus|priorit\w*|progress|how am i doing|what did i)\b"
    r"|(?:الاسبوع|الأسبوع|اسبوع|أسبوع|أولويات|اولويات)",
    re.I,
)


def review_section(db: Session, user_id: str, *, today: date, message: str) -> str:
    """For Leo, when asked about the week (or on a Monday): what is tracked, as data."""
    if not (_REVIEW_ASK.search(message or "") or today.weekday() == 0):
        return ""
    review = weekly_review(db, user_id, today=today)
    by_agent = ", ".join(f"{_agent_name(a)} {n}" for a, n in review["checkins"].items())
    lines = [f"- {as_data(review['summary'])}"]
    if by_agent:
        lines.append(f"- Check-ins by teammate: {by_agent}")
    return (
        "## The past week and the next (tracked data; totals are exact, do not recompute)\n"
        + "\n".join(lines)
    )


def _agent_name(slug: str) -> str:
    from app.agents.registry import get_agent

    agent = get_agent(slug)
    return agent.name if agent else slug


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
        "PRODID:-//Fareeq//Personal AI Team//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_ics_text(name)}",
    ]
    for uid, day, summary in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@fareeq",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_ics_text(summary[:200])}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
