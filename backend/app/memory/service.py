"""Memory persistence: two layers, strict user isolation.

* SharedMemory  -> visible to every agent for that user
* AgentMemory   -> visible only to the owning specialist (namespace = slug)
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.context import filter_shared_context
from app.agents.schema import AgentConfig
from app.db.models import AgentMemory, SharedMemory
from app.memory.extraction import Candidate
from app.memory.schemas import (
    AgentMemoryCreate,
    AgentMemoryUpdate,
    SharedMemoryCreate,
    SharedMemoryUpdate,
)

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
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
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
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
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
    db: Session, user_id: str, candidates: list[Candidate], *, source: str
) -> list[Candidate]:
    """Persist the storable candidates; return the full list (with stored flags)."""
    for c in candidates:
        if not c.stored:
            continue
        if c.scope == "shared":
            upsert_shared(
                db,
                user_id,
                SharedMemoryCreate(
                    category=c.category,
                    key=c.key,
                    value=c.value,
                    source=source,
                    confidence=c.confidence,
                    sensitive=c.sensitive,
                ),
            )
        elif c.scope == "agent" and c.agent_id:
            upsert_agent(
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
    return candidates
