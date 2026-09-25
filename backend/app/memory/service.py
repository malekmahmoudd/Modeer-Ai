"""Memory persistence: two layers, strict user isolation.

* SharedMemory  -> visible to every agent for that user
* AgentMemory   -> visible only to the owning specialist (namespace = slug)
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.context import filter_shared_context
from app.agents.schema import AgentConfig
from app.db.models import AgentMemory, SharedMemory
from app.memory.extraction import Candidate
from app.memory.keys import same_fact_keys
from app.memory.schemas import (
    AgentMemoryCreate,
    AgentMemoryUpdate,
    SharedMemoryCreate,
    SharedMemoryUpdate,
)

#: The source recorded for memories a person saved explicitly. Anything else is
#: automatic extraction, labelled with the agent that proposed it.
USER_SOURCE = "user"
#: Fields that change what a fact says. Editing one of these is the person
#: stating something; pinning or flagging is not.
CONTENT_FIELDS = frozenset({"key", "value", "category"})


#: Earlier values kept on each fact. Enough to undo a bad update; not a log.
HISTORY_LIMIT = 5


def _existing(db: Session, user_id: str, candidate: Candidate):
    """The row an automatic write would replace, if any.

    Looks under every key that names the same fact (see app/memory/keys.py),
    so "city" updates the row saved as "location" instead of starting another.
    """
    keys = same_fact_keys(candidate.key)
    if candidate.scope == "shared":
        rows = db.scalars(
            select(SharedMemory).where(SharedMemory.user_id == user_id, SharedMemory.key.in_(keys))
        )
    else:
        rows = db.scalars(
            select(AgentMemory).where(
                AgentMemory.user_id == user_id,
                AgentMemory.agent_id == candidate.agent_id,
                AgentMemory.key.in_(keys),
            )
        )
    rows = list(rows)
    # The exact key first; otherwise the oldest row, which is the one people see.
    rows.sort(key=lambda r: (r.key != candidate.key, r.created_at or datetime.min))
    return rows[0] if rows else None


def _same_value_elsewhere(db: Session, user_id: str, candidate: Candidate) -> bool:
    """Whether this value is already stored in the same category under another key.

    Only for values long enough to identify a fact: "yes" under "vegetarian"
    and "yes" under "has_car" are two facts.
    """
    value = _norm(candidate.value)
    if len(value) < 10:
        return False
    if candidate.scope == "shared":
        rows = db.scalars(select(SharedMemory).where(SharedMemory.user_id == user_id))
    else:
        rows = db.scalars(
            select(AgentMemory).where(
                AgentMemory.user_id == user_id, AgentMemory.agent_id == candidate.agent_id
            )
        )
    return any(r.category == candidate.category and _norm(r.value) == value for r in rows)


def _norm(value: str) -> str:
    return " ".join((value or "").casefold().split()).rstrip(".")


def remember_previous(row, source: str | None = None) -> None:
    """Keep the value a row is about to lose, so an update is never silent."""
    entry = {
        "value": row.value,
        "source": row.source,
        "replaced_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if source is not None:
        entry["replaced_by"] = source
    # Reassign rather than mutate: the JSON column only notices a new object.
    row.history = [*(row.history or []), entry][-HISTORY_LIMIT:]


# --- shared ---------------------------------------------------------------


def list_shared(db: Session, user_id: str) -> list[SharedMemory]:
    stmt = (
        select(SharedMemory)
        .where(SharedMemory.user_id == user_id)
        .order_by(SharedMemory.pinned.desc(), SharedMemory.category, SharedMemory.key)
    )
    return list(db.scalars(stmt))


def upsert_shared(db: Session, user_id: str, data: SharedMemoryCreate) -> SharedMemory:
    existing = db.scalar(
        select(SharedMemory).where(SharedMemory.user_id == user_id, SharedMemory.key == data.key)
    )
    if existing:
        existing.value = data.value
        existing.category = data.category
        existing.source = data.source
        existing.confidence = data.confidence
        existing.sensitive = data.sensitive
        existing.pinned = data.pinned
        if data.source == USER_SOURCE:  # a save by hand: see update_shared
            existing.history = existing.source_message_id = None
        db.flush()
        return existing
    row = SharedMemory(
        user_id=user_id,
        scope="shared",
        category=data.category,
        key=data.key,
        value=data.value,
        source=data.source,
        confidence=data.confidence,
        sensitive=data.sensitive,
        pinned=data.pinned,
    )
    db.add(row)
    db.flush()
    return row


def update_shared(
    db: Session, user_id: str, memory_id: str, data: SharedMemoryUpdate
) -> SharedMemory | None:
    row = db.scalar(
        select(SharedMemory).where(SharedMemory.id == memory_id, SharedMemory.user_id == user_id)
    )
    if row is None:
        return None
    changed = data.model_dump(exclude_unset=True)
    if "value" in changed:
        row.source_message_id = None
        # A correction by hand is often made to remove something; keeping the
        # old wording would defeat it. History records automatic updates only.
        row.history = None
    for field, value in changed.items():
        setattr(row, field, value)
    if CONTENT_FIELDS & changed.keys():
        # Editing what a fact SAYS is an explicit statement, exactly like saving
        # one: record it as the user's so a later inference cannot quietly undo
        # it. Pinning or flagging says nothing about the wording, so it leaves
        # the source alone — otherwise pinning a fact would also freeze it.
        row.source = USER_SOURCE
    db.flush()
    return row


def delete_shared(db: Session, user_id: str, memory_id: str) -> bool:
    row = db.scalar(
        select(SharedMemory).where(SharedMemory.id == memory_id, SharedMemory.user_id == user_id)
    )
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


# --- agent -------------------------------------------------------------


def list_agent(db: Session, user_id: str, agent_id: str) -> list[AgentMemory]:
    stmt = (
        select(AgentMemory)
        .where(AgentMemory.user_id == user_id, AgentMemory.agent_id == agent_id)
        .order_by(AgentMemory.category, AgentMemory.key)
    )
    return list(db.scalars(stmt))


def upsert_agent(db: Session, user_id: str, data: AgentMemoryCreate) -> AgentMemory:
    existing = db.scalar(
        select(AgentMemory).where(
            AgentMemory.user_id == user_id,
            AgentMemory.agent_id == data.agent_id,
            AgentMemory.key == data.key,
        )
    )
    if existing:
        existing.value = data.value
        existing.category = data.category
        existing.source = data.source
        existing.confidence = data.confidence
        existing.sensitive = data.sensitive
        if data.source == USER_SOURCE:
            existing.history = existing.source_message_id = None
        db.flush()
        return existing
    row = AgentMemory(
        user_id=user_id,
        agent_id=data.agent_id,
        scope="agent",
        category=data.category,
        key=data.key,
        value=data.value,
        source=data.source,
        confidence=data.confidence,
        sensitive=data.sensitive,
    )
    db.add(row)
    db.flush()
    return row


def update_agent(
    db: Session, user_id: str, memory_id: str, data: AgentMemoryUpdate
) -> AgentMemory | None:
    row = db.scalar(
        select(AgentMemory).where(AgentMemory.id == memory_id, AgentMemory.user_id == user_id)
    )
    if row is None:
        return None
    changed = data.model_dump(exclude_unset=True)
    if "value" in changed:
        row.source_message_id = None
        # A correction by hand is often made to remove something; keeping the
        # old wording would defeat it. History records automatic updates only.
        row.history = None
    for field, value in changed.items():
        setattr(row, field, value)
    if CONTENT_FIELDS & changed.keys():  # see update_shared
        row.source = USER_SOURCE
    db.flush()
    return row


def delete_agent(db: Session, user_id: str, memory_id: str) -> bool:
    row = db.scalar(
        select(AgentMemory).where(AgentMemory.id == memory_id, AgentMemory.user_id == user_id)
    )
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True


# --- context assembly / candidate application ------------------------------


def context_for_agent(
    db: Session, user_id: str, agent: AgentConfig
) -> tuple[list[SharedMemory], list[AgentMemory]]:
    shared = filter_shared_context(agent, list_shared(db, user_id))
    agent_mem = list_agent(db, user_id, agent.namespace)
    return shared, agent_mem


def apply_candidates(
    db: Session,
    user_id: str,
    candidates: list[Candidate],
    *,
    source: str,
    message_id: str | None = None,
) -> list[Candidate]:
    """Persist the storable candidates; return the full list (with stored flags).

    A fact already stored under another name for the same thing is updated in
    place (see :func:`_existing`); the same value is never stored twice; and an
    update keeps the value it replaces in the row's history and reports it.

    Automatic extraction never overrides the user. A memory saved by hand
    (source "user") is left exactly as it is, even when a later message implies
    a different value: the user's explicit statement outranks an inference. The
    candidate is reported as not stored so the reply can say so.
    """
    for c in candidates:
        if not c.stored:
            continue
        existing = _existing(db, user_id, c)
        if existing is not None and existing.source == USER_SOURCE:
            c.stored = False
            c.reason = "you saved this yourself; not overwritten automatically"
            continue
        if existing is not None:
            if _norm(existing.value) == _norm(c.value):
                c.stored = False
                c.reason = "already remembered"
                continue
            # Update the row that is there, under the name it already has.
            c.key = existing.key
            c.previous_value = existing.value
            c.reason = "updated; the earlier value is kept in its history"
            remember_previous(existing, source)
        elif _same_value_elsewhere(db, user_id, c):
            c.stored = False
            c.reason = "already remembered"
            continue
        if c.scope == "shared":
            row = upsert_shared(
                db,
                user_id,
                SharedMemoryCreate(
                    category=c.category,
                    key=c.key,
                    value=c.value,
                    source=source,
                    confidence=c.confidence,
                    sensitive=c.sensitive,
                    # Keep the pin the user set; an automatic update must not
                    # quietly unpin something they chose to keep in view.
                    pinned=bool(existing is not None and getattr(existing, "pinned", False)),
                ),
            )
        elif c.scope == "agent" and c.agent_id:
            row = upsert_agent(
                db,
                user_id,
                AgentMemoryCreate(
                    agent_id=c.agent_id,
                    category=c.category,
                    key=c.key,
                    value=c.value,
                    source=source,
                    confidence=c.confidence,
                    sensitive=c.sensitive,
                ),
            )
        else:
            continue
        # Where it was learned, so the Memory page can say why it knows this.
        row.source_message_id = message_id
    return candidates


def undo_last_update(row) -> bool:
    """Put back the value an automatic update replaced. False when there is none."""
    if not row.history:
        return False
    *rest, last = row.history
    row.value = last["value"]
    row.source = last.get("source") or row.source
    row.history = rest or None
    return True
