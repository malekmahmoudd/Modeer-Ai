from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.registry import get_agent
from app.api.deps import CurrentUser, DbSession
from app.conversations import service as convo_service
from app.conversations.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    user: CurrentUser, db: DbSession, agent_id: str | None = None
) -> list[ConversationRead]:
    return convo_service.list_conversations(db, user.id, agent_id)


@router.post("", response_model=ConversationDetail, status_code=201)
def create_conversation(
    data: ConversationCreate, user: CurrentUser, db: DbSession
) -> ConversationDetail:
    if get_agent(data.agent_id) is None:
        raise HTTPException(status_code=404, detail="Unknown agent")
    return convo_service.create_conversation(db, user.id, data.agent_id)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str, user: CurrentUser, db: DbSession
) -> ConversationDetail:
    convo = convo_service.get_conversation(db, user.id, conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, user: CurrentUser, db: DbSession):
    """Erase one conversation and its messages.

    Scoped through the user's own id, so a conversation belonging to someone
    else is indistinguishable from one that does not exist.
    """
    if not convo_service.delete_conversation(db, user.id, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
