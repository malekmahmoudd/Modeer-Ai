from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.db.models import Conversation, Message


def list_conversations(
    db: Session, user_id: str, agent_id: str | None = None
) -> list[Conversation]:
    stmt = select(Conversation).where(Conversation.user_id == user_id)
    if agent_id:
        stmt = stmt.where(Conversation.agent_id == agent_id)
    stmt = stmt.order_by(
        Conversation.last_message_at.desc().nullslast(),
        Conversation.created_at.desc(),
    )
    return list(db.scalars(stmt))


def get_conversation(
    db: Session, user_id: str, conversation_id: str
) -> Conversation | None:
    return db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )


def create_conversation(
    db: Session, user_id: str, agent_id: str
) -> Conversation:
    convo = Conversation(user_id=user_id, agent_id=agent_id)
    db.add(convo)
    db.flush()
    return convo


def get_or_create(
    db: Session, user_id: str, agent_id: str, conversation_id: str | None
) -> Conversation:
    if conversation_id:
        convo = get_conversation(db, user_id, conversation_id)
        if convo is None:
            raise KeyError("conversation not found")
        if convo.agent_id != agent_id:
            raise ValueError("conversation belongs to a different agent")
        return convo
    return create_conversation(db, user_id, agent_id)


def history(db: Session, conversation_id: str) -> list[Message]:
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        )
    )


def add_message(
    db: Session,
    convo: Conversation,
    role: str,
    content: str,
    meta: dict | None = None,
) -> Message:
    msg = Message(
        conversation_id=convo.id, role=role, content=content, meta=meta or {}
    )
    db.add(msg)
    convo.last_message_at = utcnow()
    if role == "user" and convo.title == "New conversation":
        convo.title = (content.strip().splitlines()[0] or "New conversation")[:80]
    db.flush()
    return msg
