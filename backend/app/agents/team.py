"""How the team works together: what Leo can see, goal changes, handoffs.

Agents still never read each other's transcripts. What crosses between them is
narrow and visible to the person:

* Leo sees the titles of recent conversations and when they happened, plus
  the handoff notes waiting for teammates. Never what was said.
* Leo applies goal changes the person explicitly asked for.
* Any agent can pass a short note to a named teammate when the person asks.
  It is stored as that teammate's private note (category "handoff"), so it
  appears on the Memory page, where the person can read or delete it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.registry import get_agent
from app.conversations import service as convo_service
from app.core.text import as_data
from app.db.models import AgentMemory, Goal
from app.goals import service as goal_service
from app.goals.schemas import GoalCreate, GoalUpdate
from app.memory.llm_extraction import GoalChange, Handoff
from app.memory.sensitivity import looks_sensitive
from app.memory.service import remember_previous

HANDOFF = "handoff"
#: Lines of activity Leo gets. Titles only, so this stays small.
ACTIVITY_LIMIT = 8


def _name(slug: str) -> str:
    agent = get_agent(slug)
    return agent.name if agent else slug


def _when(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return "not yet"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    days = (now.date() - moment.astimezone(now.tzinfo or UTC).date()).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


def recent_activity(
    db: Session, user_id: str, *, exclude_conversation: str, now: datetime
) -> list[str]:
    """What Leo is told about the rest of the team: one line per item."""
    lines: list[str] = []
    for convo in convo_service.list_conversations(db, user_id):
        if convo.id == exclude_conversation or convo.last_message_at is None:
            continue
        if convo.agent_id == "modeer":
            continue
        # A title is the first line of the user's first message, so it can be
        # as private as the chat. Leo gets the topic only when it is not.
        title = "(a private topic)" if looks_sensitive(convo.title) else as_data(convo.title[:80])
        lines.append(f'{_name(convo.agent_id)}: "{title}" ({_when(convo.last_message_at, now)})')
        if len(lines) >= ACTIVITY_LIMIT:
            break
    for note in db.scalars(
        select(AgentMemory).where(AgentMemory.user_id == user_id, AgentMemory.category == HANDOFF)
    ):
        lines.append(f"Note waiting for {_name(note.agent_id)}: {as_data(note.value[:160])}")
        if len(lines) >= ACTIVITY_LIMIT + 4:
            break
    return lines


def apply_goal_changes(db: Session, user_id: str, changes: list[GoalChange]) -> None:
    """Apply what the person asked for; mark each change applied or say why not."""
    for change in changes:
        if change.op == "add":
            existing = {
                g.title.casefold()
                for g in goal_service.list_goals(db, user_id)
                if g.status != "done"
            }
            if change.title.casefold() in existing:
                change.reason = "already one of your goals"
                continue
            target = (
                datetime.combine(change.target_date, time(12, 0))
                if isinstance(change.target_date, date)
                else None
            )
            goal = goal_service.create_goal(
                db,
                user_id,
                GoalCreate(title=change.title, priority=change.priority or 3, target_date=target),
            )
            change.goal_id, change.applied, change.reason = goal.id, True, "added"
            continue
        goal = db.get(Goal, change.goal_id) if change.goal_id else None
        if goal is None or goal.user_id != user_id:
            change.reason = "goal not found"
            continue
        update = {
            "done": GoalUpdate(status="done"),
            "pause": GoalUpdate(status="paused"),
            "resume": GoalUpdate(status="active"),
            "priority": GoalUpdate(priority=change.priority),
        }[change.op]
        goal_service.update_goal(db, user_id, goal.id, update)
        change.applied = True
        change.reason = {
            "done": "marked done",
            "pause": "paused",
            "resume": "active again",
            "priority": f"now priority {change.priority}",
        }[change.op]


def apply_handoffs(db: Session, user_id: str, handoffs: list[Handoff], *, source: str) -> None:
    """Leave each note with its teammate. One note per sender: a newer one
    replaces the older, which is kept in the note's history."""
    for handoff in handoffs:
        if not handoff.stored:
            continue
        key = f"from_{source}"
        note = db.scalar(
            select(AgentMemory).where(
                AgentMemory.user_id == user_id,
                AgentMemory.agent_id == handoff.agent_id,
                AgentMemory.key == key,
            )
        )
        if note is None:
            db.add(
                AgentMemory(
                    user_id=user_id,
                    agent_id=handoff.agent_id,
                    scope="agent",
                    category=HANDOFF,
                    key=key,
                    value=handoff.brief,
                    source=source,
                    confidence=1.0,
                    sensitive=False,
                )
            )
        else:
            remember_previous(note, source)
            note.value, note.category, note.source = handoff.brief, HANDOFF, source
        db.flush()


def as_events(changes: list[GoalChange], handoffs: list[Handoff]) -> dict:
    """The parts of the memory event that report goal changes and handoffs."""
    return {
        "goal_changes": [
            {
                "op": c.op,
                "title": c.title,
                "goal_id": c.goal_id,
                "priority": c.priority,
                "target_date": c.target_date.isoformat() if c.target_date else None,
                "applied": c.applied,
                "reason": c.reason,
            }
            for c in changes
        ],
        "handoffs": [
            {
                "agent_id": h.agent_id,
                "agent_name": _name(h.agent_id),
                "brief": h.brief,
                "stored": h.stored,
                "reason": h.reason,
            }
            for h in handoffs
        ],
    }
