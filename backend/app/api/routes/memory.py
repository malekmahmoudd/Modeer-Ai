from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

from app.agents.registry import get_agent
from app.api.deps import CurrentUser, DbSession
from app.memory import service
from app.memory.schemas import (
    AgentMemoryCreate,
    AgentMemoryRead,
    AgentMemoryUpdate,
    SharedMemoryCreate,
    SharedMemoryRead,
    SharedMemoryUpdate,
)

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
def update_shared(
    memory_id: str, data: SharedMemoryUpdate, user: CurrentUser, db: DbSession
):
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
def update_agent_memory(
    memory_id: str, data: AgentMemoryUpdate, user: CurrentUser, db: DbSession
):
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
