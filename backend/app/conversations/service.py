from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
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


def next_timestamp(db: Session, conversation_id: str) -> datetime:
    """A time strictly later than every message already in this conversation.

    Messages are ordered by ``created_at``, and a clock is not guaranteed to
    tick between two writes — Windows moves in ~15ms steps, so a question and
    its answer can land on the same instant. The order then falls back to a
    random id, which puts the reply before the question about half the time:
    the model sees the turn backwards and a retry cannot tell what came last.
    """
    latest = db.scalar(
        select(func.max(Message.created_at)).where(Message.conversation_id == conversation_id)
    )
    now = utcnow()
    if latest is None:
        return now
    if latest.tzinfo is None:  # SQLite hands back naive datetimes
        latest = latest.replace(tzinfo=UTC)
    return now if now > latest else latest + timedelta(milliseconds=1)


def add_message(
    db: Session,
    convo: Conversation,
    role: str,
    content: str,
    meta: dict | None = None,
) -> Message:
    when = next_timestamp(db, convo.id)
    msg = Message(
        conversation_id=convo.id, role=role, content=content, meta=meta or {}, created_at=when
    )
    db.add(msg)
    convo.last_message_at = when
    if role == "user" and convo.title == "New conversation":
        convo.title = (content.strip().splitlines()[0] or "New conversation")[:80]
    db.flush()
    return msg


def delete_conversation(db: Session, user_id: str, conversation_id: str) -> bool:
    """Delete a conversation the user owns. Messages cascade. False if not theirs."""
    convo = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if convo is None:
        return False
    db.delete(convo)
    db.flush()
    return True


def completion_of(message: Message) -> str:
    """How an assistant message ended. Rows written before statuses existed
    were only ever saved on success, so a missing status means completed."""
    return (message.meta or {}).get("completion", "completed")


def history_for_model(messages: list[Message]) -> list[Message]:
    """The turns worth showing the model: everything except failed placeholders.

    A failed reply is an empty row kept so the person can see what happened and
    retry; sent to the model it would be an empty assistant turn.
    """
    return [m for m in messages if not (m.role == "assistant" and completion_of(m) == "failed")]


class NothingToRetry(ValueError):
    """The latest turn already has a finished reply."""


def prepare_retry(db: Session, convo: Conversation) -> Message:
    """Clear the latest turn's unfinished reply and return its user message.

    Retrying regenerates that turn in place: the user's message is reused, never
    written again, so a retry cannot duplicate it. Only an unfinished turn can
    be retried — regenerating a completed reply would spend quota the person did
    not ask to spend.
    """
    messages = history(db, convo.id)
    last_user = next((m for m in reversed(messages) if m.role == "user"), None)
    if last_user is None:
        raise NothingToRetry("There is no message to retry.")
    replies = messages[messages.index(last_user) + 1 :]
    if any(completion_of(m) == "completed" for m in replies):
        raise NothingToRetry("The latest reply already finished; there is nothing to retry.")
    for reply in replies:
        db.delete(reply)
    db.flush()
    return last_user
