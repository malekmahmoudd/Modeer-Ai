from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.agents.registry import get_agent, require_agent
from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.usage import limited_caller
from app.db.models import AgentMemory, Conversation, Message, SharedMemory
from app.llm.provider import get_llm_provider, resolve_model
from app.memory import service
from app.memory.llm_extraction import analyze_turn
from app.memory.schemas import (
    AgentMemoryCreate,
    AgentMemoryRead,
    AgentMemoryUpdate,
    SharedMemoryCreate,
    SharedMemoryRead,
    SharedMemoryUpdate,
)
from app.memory.sensitivity import looks_sensitive

router = APIRouter(prefix="/memory", tags=["memory"])

#: One label per fact, per person. Renaming a label onto one that already exists
#: is an ordinary mistake on the Memory page, so it gets an answer the person
#: can act on — not a 500, which would also count as an unhandled error and
#: page the operator.
TAKEN = "You already have a fact with that label. Edit that one, or pick another label."


# --- shared ---------------------------------------------------------------


@router.get("/shared", response_model=list[SharedMemoryRead])
def list_shared(user: CurrentUser, db: DbSession):
    return service.list_shared(db, user.id)


@router.post("/shared", response_model=SharedMemoryRead, status_code=201)
def create_shared(data: SharedMemoryCreate, user: CurrentUser, db: DbSession):
    # Always the user's own save, whatever the body claims: the source is what
    # protects it from being overwritten by automatic extraction later.
    explicit = data.model_copy(update={"source": service.USER_SOURCE})
    return service.upsert_shared(db, user.id, explicit)


@router.patch("/shared/{memory_id}", response_model=SharedMemoryRead)
def update_shared(memory_id: str, data: SharedMemoryUpdate, user: CurrentUser, db: DbSession):
    try:
        row = service.update_shared(db, user.id, memory_id, data)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=TAKEN) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return row


@router.delete("/shared/{memory_id}", status_code=204)
def delete_shared(memory_id: str, user: CurrentUser, db: DbSession):
    if not service.delete_shared(db, user.id, memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")


# --- agent -------------------------------------------------------------


@router.get("/agent/{agent_id}", response_model=list[AgentMemoryRead])
def list_agent(agent_id: str, user: CurrentUser, db: DbSession):
    if get_agent(agent_id) is None:
        raise HTTPException(status_code=404, detail="Unknown agent")
    return service.list_agent(db, user.id, agent_id)


@router.post("/agent", response_model=AgentMemoryRead, status_code=201)
def create_agent_memory(data: AgentMemoryCreate, user: CurrentUser, db: DbSession):
    if get_agent(data.agent_id) is None:
        raise HTTPException(status_code=404, detail="Unknown agent")
    explicit = data.model_copy(update={"source": service.USER_SOURCE})
    return service.upsert_agent(db, user.id, explicit)


@router.patch("/agent/{memory_id}", response_model=AgentMemoryRead)
def update_agent_memory(memory_id: str, data: AgentMemoryUpdate, user: CurrentUser, db: DbSession):
    try:
        row = service.update_agent(db, user.id, memory_id, data)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=TAKEN) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return row


@router.delete("/agent/{memory_id}", status_code=204)
def delete_agent_memory(memory_id: str, user: CurrentUser, db: DbSession):
    if not service.delete_agent(db, user.id, memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")


# --- where a fact came from, and undoing an automatic update -------------------------


def _row(db, user_id: str, scope: str, memory_id: str):
    model = {"shared": SharedMemory, "agent": AgentMemory}.get(scope)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown memory layer")
    row = db.scalar(select(model).where(model.id == memory_id, model.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return row


@router.get("/{scope}/{memory_id}/source")
def memory_source(scope: str, memory_id: str, user: CurrentUser, db: DbSession) -> dict:
    """Why the team knows this: the message it was learned from, and its history."""
    row = _row(db, user.id, scope, memory_id)
    origin = None
    if row.source_message_id:
        found = db.execute(
            select(Message, Conversation)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Message.id == row.source_message_id, Conversation.user_id == user.id)
        ).first()
        if found is not None:
            message, conversation = found
            origin = {
                "message_id": message.id,
                "conversation_id": conversation.id,
                "agent_id": conversation.agent_id,
                "said_at": message.created_at.isoformat() if message.created_at else None,
                "excerpt": message.content[:300],
            }
    return {
        "id": row.id,
        "source": row.source,
        "saved_by_you": row.source == service.USER_SOURCE,
        "learned_from": origin,
        "history": row.history or [],
    }


@router.post("/{scope}/{memory_id}/undo")
def undo_memory_update(scope: str, memory_id: str, user: CurrentUser, db: DbSession) -> dict:
    """Put back the value the last automatic update replaced."""
    row = _row(db, user.id, scope, memory_id)
    if not service.undo_last_update(row):
        raise HTTPException(status_code=409, detail="There is no earlier value to go back to.")
    db.flush()
    return {"id": row.id, "value": row.value, "history": row.history or []}


# --- importing from another assistant ------------------------------------------------------

#: One import reads at most this much text, in a few model calls.
IMPORT_CHARS = 18000
IMPORT_CHUNK = 6000


class ImportText(BaseModel):
    text: str = Field(min_length=20, max_length=200_000)


class ImportFact(BaseModel):
    category: str = Field(default="general", max_length=48)
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=500)


class ImportChoice(BaseModel):
    facts: list[ImportFact] = Field(min_length=1, max_length=60)


@router.post("/import/preview")
async def import_preview(
    data: ImportText,
    _caller: Annotated[str | None, Depends(limited_caller)],
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """The facts about the person in text from another assistant (a ChatGPT or
    Claude memory export, notes, a bio). Nothing is saved: they tick what to keep."""
    text = data.text.strip()
    chunks = [
        text[i : i + IMPORT_CHUNK] for i in range(0, min(len(text), IMPORT_CHARS), IMPORT_CHUNK)
    ]
    known = {row.key for row in service.list_shared(db, user.id)}
    seen: dict[str, dict] = {}
    for chunk in chunks:
        analysis = await analyze_turn(
            chunk,
            agent_id="modeer",
            provider=get_llm_provider(),
            model=resolve_model(settings.memory_model or require_agent("modeer").model.model),
            known_keys=sorted(known | set(seen)),
            about_me=True,
        )
        for fact in analysis.facts:
            weak = fact.confidence < settings.memory_min_confidence
            if fact.scope != "shared" or weak or fact.key in seen:
                continue
            seen[fact.key] = {
                "category": fact.category,
                "key": fact.key,
                "value": fact.value,
                "sensitive": bool(fact.sensitive)
                or looks_sensitive(fact.value, category=fact.category),
                "replaces": fact.key in known,
            }
    return {"facts": list(seen.values()), "truncated": len(text) > IMPORT_CHARS}


@router.post("/import/apply")
def import_apply(data: ImportChoice, user: CurrentUser, db: DbSession) -> dict:
    """Save the facts the person ticked, as their own saves."""
    for fact in data.facts:
        service.upsert_shared(
            db,
            user.id,
            SharedMemoryCreate(
                category=fact.category,
                key=fact.key,
                value=fact.value,
                source=service.USER_SOURCE,
                sensitive=looks_sensitive(fact.value, category=fact.category),
            ),
        )
    return {"saved": len(data.facts)}
