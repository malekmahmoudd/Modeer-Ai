from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.registry import get_agent
from app.api.deps import CurrentUser, DbSession
from app.conversations import service as convo_service
from app.conversations.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationRename,
    PinnedReply,
    PinUpdate,
    RewindRequest,
    RewindResult,
    SearchHit,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
def list_conversations(
    user: CurrentUser, db: DbSession, agent_id: str | None = None
) -> list[ConversationRead]:
    return convo_service.list_conversations(db, user.id, agent_id)


@router.get("/search", response_model=list[SearchHit])
def search_conversations(q: str, user: CurrentUser, db: DbSession) -> list[dict]:
    """Every message and title containing ``q``, across all agents."""
    return convo_service.search(db, user.id, q[:200])


@router.get("/recent", response_model=list[ConversationRead])
def recent_conversations(user: CurrentUser, db: DbSession) -> list[ConversationRead]:
    """The latest conversations with any teammate, for the home page."""
    return convo_service.recent(db, user.id)


@router.get("/pinned", response_model=list[PinnedReply])
def pinned_replies(user: CurrentUser, db: DbSession) -> list[PinnedReply]:
    """Replies the person saved."""
    return [
        PinnedReply(
            message_id=m.id,
            conversation_id=c.id,
            agent_id=c.agent_id,
            title=c.title,
            content=m.content,
            pinned_at=m.pinned_at,
        )
        for m, c in convo_service.pinned(db, user.id)
    ]


@router.post("", response_model=ConversationDetail, status_code=201)
def create_conversation(
    data: ConversationCreate, user: CurrentUser, db: DbSession
) -> ConversationDetail:
    if get_agent(data.agent_id) is None:
        raise HTTPException(status_code=404, detail="Unknown agent")
    return convo_service.create_conversation(db, user.id, data.agent_id)


@router.patch("/{conversation_id}", response_model=ConversationRead)
def rename_conversation(
    conversation_id: str, data: ConversationRename, user: CurrentUser, db: DbSession
) -> ConversationRead:
    convo = convo_service.rename(db, user.id, conversation_id, data.title)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo


@router.post("/{conversation_id}/rewind", response_model=RewindResult)
def rewind_conversation(
    conversation_id: str, data: RewindRequest, user: CurrentUser, db: DbSession
) -> RewindResult:
    """Take back the latest turn: its reply (regenerate) or the whole turn (edit).

    Regenerate is followed by the usual retry, which answers the same message
    again; edit returns the message text for the person to change and resend.
    """
    convo = convo_service.get_conversation(db, user.id, conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        text = convo_service.rewind(db, convo, keep_question=data.mode == "regenerate")
    except convo_service.NothingToRewind as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RewindResult(text=text)


@router.patch("/{conversation_id}/messages/{message_id}", status_code=204)
def pin_message(
    conversation_id: str, message_id: str, data: PinUpdate, user: CurrentUser, db: DbSession
):
    """Save a reply to "Saved replies", or remove it from there."""
    msg = convo_service.set_pinned(db, user.id, message_id, data.pinned)
    if msg is None or msg.conversation_id != conversation_id:
        raise HTTPException(status_code=404, detail="Reply not found")


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, user: CurrentUser, db: DbSession) -> ConversationDetail:
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
