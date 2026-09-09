from __future__ import annotations

from fastapi import APIRouter, HTTPException

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


# --- shared ---------------------------------------------------------------

@router.get("/shared", response_model=list[SharedMemoryRead])
def list_shared(user: CurrentUser, db: DbSession):
    return service.list_shared(db, user.id)


@router.post("/shared", response_model=SharedMemoryRead, status_code=201)
def create_shared(data: SharedMemoryCreate, user: CurrentUser, db: DbSession):
    return service.upsert_shared(db, user.id, data)


@router.patch("/shared/{memory_id}", response_model=SharedMemoryRead)
def update_shared(
    memory_id: str, data: SharedMemoryUpdate, user: CurrentUser, db: DbSession
):
    row = service.update_shared(db, user.id, memory_id, data)
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
    return service.upsert_agent(db, user.id, data)


@router.patch("/agent/{memory_id}", response_model=AgentMemoryRead)
def update_agent_memory(
    memory_id: str, data: AgentMemoryUpdate, user: CurrentUser, db: DbSession
):
    row = service.update_agent(db, user.id, memory_id, data)
    if row is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return row


@router.delete("/agent/{memory_id}", status_code=204)
def delete_agent_memory(memory_id: str, user: CurrentUser, db: DbSession):
    if not service.delete_agent(db, user.id, memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")
