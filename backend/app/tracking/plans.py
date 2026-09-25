"""Saved plans: a plan an agent wrote, kept as a checklist.

Saving is deterministic and costs no model call. When the person says "save
this plan", the agent's previous reply is split into steps: list items,
numbered lines, "Day 3 — …" lines, table rows. "Day N" and "Week N" steps get
dates counted from the day it was saved. Progress is marked from chat ("done
with day 3") or through the API.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message, Plan, PlanStep

MAX_STEPS = 40
MAX_STEP_CHARS = 300
MIN_STEPS = 2

#: "save this plan", "keep that schedule", "save it". Not "track": "track my
#: progress on this plan" is not a request to save a new one.
_SAVE = re.compile(
    r"\b(?:save|keep|store)\s+(?:this|that|the|your|it|my)\b[^.?!\n]{0,25}?"
    r"\b(?:plan|schedule|programme|program|routine|itinerary|checklist|timetable|"
    r"workout|block|split)s?\b"
    r"|\badd (?:this|that|it) to my plans\b"
    r"|\bsave (?:it|this|that)\s*(?:[.!]|$)",
    re.I,
)
_SAVE_AR = re.compile(r"(?:احفظ|خزن|سجل)\s+(?:لي\s+)?(?:هذه\s+|هذا\s+)?(?:ال)?(?:خطه|جدول|برنامج)")
#: "done with day 3", "finished week 2", "completed step 4", "did day 1",
#: "day 3 done". A verb right before the step, or "done" right after it: "did 3
#: sets of 10, day 4 of my streak" is not progress on the plan.
_PROGRESS = re.compile(
    r"\b(?:done with|finished|completed|ticked off|through with)\b[^.?!\n]{0,20}?"
    r"\b(day|week|step|session)\s*(\d{1,2})\b"
    r"|\bdid\s+(day|week|step|session)\s*(\d{1,2})\b"
    r"|\b(day|week|step|session)\s*(\d{1,2})\s+(?:is\s+)?(?:done|finished|complete)\b",
    re.I,
)
_PROGRESS_AR = re.compile(
    r"(?:خلصت|انهيت|انتهيت|خلصنا|عملت)\s+(?:من\s+)?(?:ال)?(يوم|اسبوع|خطوه)\s*(\d{1,2})"
)
_AR_UNIT = {"يوم": "day", "اسبوع": "week", "خطوه": "step"}
#: A sentence that says it has not happened, or asks: "I haven't done day 3",
#: "how did week 2 go?", "don't save this plan".
_NEGATION = re.compile(
    r"\b(?:not|never|haven'?t|hasn'?t|didn'?t|don'?t|won'?t|isn'?t|yet|no)\b|n't\b"
    r"|(?:^|\s)(?:لم|لا|ما|مش|مو|لسه|لسا)(?:\s|$)",
    re.I,
)
_SENTENCE = re.compile(r"[^.!?؟\n]+[.!?؟]?")
#: "shift my plan", "restart the plan from today", "reschedule this programme".
_SHIFT = re.compile(
    r"\b(?:shift|move|push|reschedule|restart)\s+(?:back\s+)?(?:my|the|this)\s+"
    r"(?:plan|schedule|programme|program|block)\b",
    re.I,
)

_ITEM = re.compile(r"^\s*(?:[-*•]\s+|\d{1,2}[.)]\s+)(.+)$")
_DAYISH = re.compile(
    r"^\s*[#*\s]*(day|days|week|weeks|session|يوم|اليوم|اسبوع|الاسبوع)\s*(\d{1,2})"
    r"(?:\s*[-–]\s*\d{1,2})?\b",
    re.I,
)
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_WEEKDAY = re.compile(
    r"^\s*[#*\s]*(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b|\((mon|tue|wed|thu|fri|sat|sun)[a-z]*\)",
    re.I,
)
_HEADING = re.compile(r"^\s*#{1,4}\s+(.+?)\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}")


def _fold(text: str) -> str:
    from app.memory.sensitivity import _fold as fold

    return fold(text or "")


def _statements(message: str):
    """Sentences that neither ask nor deny."""
    for sentence in _SENTENCE.findall(_fold(message)):
        if sentence.rstrip().endswith(("?", "؟")) or _NEGATION.search(sentence):
            continue
        yield sentence


def asks_to_save(message: str) -> bool:
    """Whether the person asks to keep a plan as a checklist."""
    return any(_SAVE.search(s) or _SAVE_AR.search(s) for s in _statements(message))


def asks_to_shift(message: str) -> bool:
    return any(_SHIFT.search(s) for s in _statements(message))


def progress_named(message: str) -> list[tuple[str, int]]:
    """The (unit, number) pairs the person says they have done."""
    found: list[tuple[str, int]] = []
    for sentence in _statements(message):
        for match in _PROGRESS.finditer(sentence):
            groups = [g for g in match.groups() if g]
            found.append((_unit(groups[0]), int(groups[1])))
        for match in _PROGRESS_AR.finditer(sentence):
            found.append((_AR_UNIT[match.group(1)], int(match.group(2))))
    return found


def _unit(word: str) -> str:
    word = word.lower().rstrip("s")
    return "day" if word == "session" else word


def _clean(text: str) -> str:
    text = re.sub(r"[*_`#]+", "", text)
    return " ".join(text.split())[:MAX_STEP_CHARS]


def _is_dated(text: str) -> bool:
    folded = _fold(text)
    return bool(_DAYISH.match(folded) or _WEEKDAY.search(folded))


def parse_steps(reply: str) -> tuple[str | None, list[str]]:
    """The reply's title (first heading, if any) and its steps, in order.

    A "## Day 1 — Upper body" heading is a step, not the title, and the list
    under it belongs to it: "Day 1 — Upper body: Push-ups; Rows".
    """
    title: str | None = None
    steps: list[str] = []
    grouping = False  # the last step is a Day/Week heading collecting its list
    table_header_seen = False
    for line in (reply or "").splitlines():
        if not line.strip():
            continue
        if heading := _HEADING.match(line):
            text = _clean(heading.group(1))
            if _is_dated(text):
                steps.append(text)
                grouping = True
            else:
                title = title or text
                grouping = False
            continue
        if line.strip().startswith("|"):
            grouping = False
            if _TABLE_SEPARATOR.match(line.strip().lstrip("|")):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not table_header_seen:
                # The first row of a table is its header.
                table_header_seen = True
                continue
            text = " — ".join(c for c in cells if c)
            if text:
                steps.append(_clean(text))
            continue
        if item := _ITEM.match(line):
            text = _clean(item.group(1))
            if grouping and steps and not _is_dated(text):
                joiner = ": " if ":" not in steps[-1] else "; "
                steps[-1] = (steps[-1] + joiner + text)[:MAX_STEP_CHARS]
            else:
                steps.append(text)
                grouping = False
        elif _is_dated(line):
            steps.append(_clean(line))
            grouping = False
    return title, [s for s in steps if len(s) >= 2][:MAX_STEPS]


def _next_weekday(start: date, weekday: int) -> date:
    return start + timedelta(days=(weekday - start.weekday()) % 7)


def _due(step: str, starts_on: date) -> date | None:
    """The day a step falls on: "Day 3", "Week 2", "Mon", "Day 2 (Wed)".

    "Day N" counts from the day the plan starts; a weekday named with it wins,
    taking the first such weekday on or after that day.
    """
    folded = _fold(step)
    day = _WEEKDAY.search(folded)
    weekday = _WEEKDAYS.index((day.group(1) or day.group(2)).lower()[:3]) if day else None
    match = _DAYISH.match(folded)
    if match:
        n = int(match.group(2))
        if n < 1:
            return None
        unit = _AR_UNIT.get(match.group(1).removeprefix("ال"), _unit(match.group(1)))
        base = starts_on + timedelta(days=(n - 1) * (7 if unit == "week" else 1))
        return _next_weekday(base, weekday) if weekday is not None else base
    if weekday is not None:
        return _next_weekday(starts_on, weekday)
    return None


def save_from_reply(
    db: Session,
    user_id: str,
    agent_id: str,
    reply: Message,
    *,
    today: date,
    fallback_title: str,
) -> Plan | None:
    """Save the plan in ``reply``, or None when it has no steps to keep."""
    existing = db.scalar(
        select(Plan).where(Plan.user_id == user_id, Plan.source_message_id == reply.id)
    )
    if existing is not None:
        return existing
    title, steps = parse_steps(reply.content)
    if len(steps) < MIN_STEPS:
        return None
    plan = Plan(
        user_id=user_id,
        agent_id=agent_id,
        title=(title or fallback_title)[:200],
        starts_on=today,
        source_message_id=reply.id,
    )
    plan.steps = [
        PlanStep(position=i, text=text, due_on=_due(text, today)) for i, text in enumerate(steps, 1)
    ]
    db.add(plan)
    db.flush()
    return plan


def mark_progress(db: Session, user_id: str, agent_id: str, message: str) -> list[PlanStep]:
    """Tick off the steps named in ``message`` on the latest active plan — this
    agent's, or anyone's when it is Leo, who sees every plan."""
    named = progress_named(message)
    if not named:
        return []
    plan = latest_active(db, user_id, None if agent_id == "modeer" else agent_id)
    if plan is None:
        return []
    ticked: list[PlanStep] = []
    for unit, n in named:
        step = _find_step(plan, unit, n)
        if step is not None and step.done_at is None:
            step.done_at = datetime.now(UTC)
            ticked.append(step)
    _close_if_finished(plan)
    db.flush()
    return ticked


def reschedule(plan: Plan, starts_on: date) -> None:
    """Date every step again from a new start day."""
    plan.starts_on = starts_on
    for step in plan.steps:
        step.due_on = _due(step.text, starts_on)


def shift_remaining(plan: Plan, today: date) -> int:
    """Move the steps not yet done so the next one falls today. Missing a day
    should not leave every later step overdue. Returns the days moved."""
    upcoming = [s for s in plan.steps if s.done_at is None and s.due_on]
    if not upcoming or upcoming[0].due_on >= today:
        return 0
    offset = today - upcoming[0].due_on
    for step in upcoming:
        step.due_on += offset
    return offset.days


def _find_step(plan: Plan, unit: str, n: int) -> PlanStep | None:
    if unit == "step":
        return next((s for s in plan.steps if s.position == n), None)
    for step in plan.steps:
        match = _DAYISH.match(_fold(step.text))
        if not match or int(match.group(2)) != n:
            continue
        word = match.group(1).removeprefix("ال")
        if _AR_UNIT.get(word, _unit(word)) == unit:
            return step
    return None


def _close_if_finished(plan: Plan) -> None:
    if plan.steps and all(s.done_at for s in plan.steps):
        plan.status = "done"
    elif plan.status == "done":
        plan.status = "active"


def set_step(db: Session, plan: Plan, step_id: str, done: bool) -> PlanStep | None:
    step = next((s for s in plan.steps if s.id == step_id), None)
    if step is None:
        return None
    step.done_at = (step.done_at or datetime.now(UTC)) if done else None
    _close_if_finished(plan)
    db.flush()
    return step


def latest_active(db: Session, user_id: str, agent_id: str | None) -> Plan | None:
    stmt = select(Plan).where(Plan.user_id == user_id, Plan.status == "active")
    if agent_id is not None:
        stmt = stmt.where(Plan.agent_id == agent_id)
    return db.scalar(stmt.order_by(Plan.created_at.desc()))


def list_plans(db: Session, user_id: str, *, status: str | None = None) -> list[Plan]:
    stmt = select(Plan).where(Plan.user_id == user_id)
    if status:
        stmt = stmt.where(Plan.status == status)
    return list(db.scalars(stmt.order_by(Plan.created_at.desc())))


def get_plan(db: Session, user_id: str, plan_id: str) -> Plan | None:
    return db.scalar(select(Plan).where(Plan.id == plan_id, Plan.user_id == user_id))


def progress_line(plan: Plan, today: date) -> str:
    """A line like "Revision: 5/14 done; next: Day 6 — past paper (due Wed 30 Sep)"."""
    done = sum(1 for s in plan.steps if s.done_at)
    line = f"{plan.title}: {done}/{len(plan.steps)} done"
    upcoming = next((s for s in plan.steps if s.done_at is None), None)
    if upcoming is not None:
        line += f"; next: {upcoming.text[:120]}"
        if upcoming.due_on:
            # "not ticked yet", not "overdue": a missed day is not a failure.
            late = " — not ticked yet" if upcoming.due_on < today else ""
            line += f" (due {upcoming.due_on:%a} {upcoming.due_on.day} {upcoming.due_on:%b}{late})"
    return line
