from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utcnow
from app.db.models import Conversation, Message

#: An incognito chat is deleted this long after it starts, if the person has
#: not closed it first.
INCOGNITO_HOURS = 24


def purge_incognito(db: Session, user_id: str | None = None, *, now: datetime | None = None) -> int:
    """Delete incognito conversations past their time. One account, or all."""
    now = (now or utcnow()).replace(tzinfo=None)
    stmt = select(Conversation.id).where(
        Conversation.incognito.is_(True), Conversation.expires_at <= now
    )
    if user_id:
        stmt = stmt.where(Conversation.user_id == user_id)
    ids = list(db.scalars(stmt))
    if ids:
        db.execute(delete(Message).where(Message.conversation_id.in_(ids)))
        db.execute(delete(Conversation).where(Conversation.id.in_(ids)))
        db.flush()
    return len(ids)


def list_conversations(
    db: Session, user_id: str, agent_id: str | None = None
) -> list[Conversation]:
    """The person's conversations, newest first. Incognito ones never list."""
    purge_incognito(db, user_id)
    stmt = select(Conversation).where(
        Conversation.user_id == user_id, Conversation.incognito.is_(False)
    )
    if agent_id:
        stmt = stmt.where(Conversation.agent_id == agent_id)
    stmt = stmt.order_by(
        Conversation.last_message_at.desc().nullslast(),
        Conversation.created_at.desc(),
    )
    return list(db.scalars(stmt))


def get_conversation(db: Session, user_id: str, conversation_id: str) -> Conversation | None:
    return db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )


def create_conversation(
    db: Session,
    user_id: str,
    agent_id: str,
    *,
    incognito: bool = False,
    incognito_context: bool = False,
) -> Conversation:
    convo = Conversation(user_id=user_id, agent_id=agent_id)
    if incognito:
        convo.incognito = True
        convo.incognito_context = incognito_context
        convo.expires_at = (utcnow() + timedelta(hours=INCOGNITO_HOURS)).replace(tzinfo=None)
    db.add(convo)
    db.flush()
    return convo


def get_or_create(
    db: Session,
    user_id: str,
    agent_id: str,
    conversation_id: str | None,
    *,
    incognito: bool = False,
    incognito_context: bool = False,
) -> Conversation:
    if conversation_id:
        convo = get_conversation(db, user_id, conversation_id)
        if convo is None:
            raise KeyError("conversation not found")
        if convo.agent_id != agent_id:
            raise ValueError("conversation belongs to a different agent")
        return convo
    return create_conversation(
        db, user_id, agent_id, incognito=incognito, incognito_context=incognito_context
    )


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


# --- finding, naming, rewinding, saving ------------------------------------------------

_ARABIC_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي"})
_SEARCH_LIMIT = 30
_SNIPPET = 160


def _fold(text: str) -> str:
    return text.translate(_ARABIC_FOLD).casefold()


def _snippet(content: str, needle: str) -> str:
    """The words around the first match, on one line."""
    flat = re.sub(r"\s+", " ", content)
    at = _fold(flat).find(needle)
    if at < 0:
        return flat[:_SNIPPET]
    start = max(0, at - _SNIPPET // 3)
    piece = flat[start : start + _SNIPPET]
    return ("…" if start else "") + piece + ("…" if start + _SNIPPET < len(flat) else "")


def search(db: Session, user_id: str, query: str) -> list[dict]:
    """Messages and titles containing ``query``, newest first, across every agent.

    A plain substring match: at one person's scale it needs no index. Arabic
    letter variants (alef forms, taa marbuta, alef maqsura) match each other.
    Incognito chats are never searched.
    """
    needle = _fold(query.strip())
    if len(needle) < 2:
        return []
    rows = db.execute(
        select(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == user_id,
            Conversation.incognito.is_(False),
            Message.role.in_(("user", "assistant")),
        )
        .order_by(Message.created_at.desc())
    ).all()
    hits: list[dict] = []
    seen_titles: set[str] = set()
    for msg, convo in rows:
        in_title = needle in _fold(convo.title or "")
        if needle not in _fold(msg.content or "") and not (
            in_title and convo.id not in seen_titles
        ):
            continue
        seen_titles.add(convo.id)
        hits.append(
            {
                "conversation_id": convo.id,
                "agent_id": convo.agent_id,
                "title": convo.title,
                "message_id": msg.id,
                "role": msg.role,
                "snippet": _snippet(msg.content or "", needle),
                "created_at": msg.created_at,
            }
        )
        if len(hits) >= _SEARCH_LIMIT:
            break
    return hits


def rename(db: Session, user_id: str, conversation_id: str, title: str) -> Conversation | None:
    convo = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if convo is None:
        return None
    convo.title = title.strip()[:200]
    db.flush()
    return convo


class NothingToRewind(ValueError):
    """There is no finished last turn to take back."""


def rewind(db: Session, convo: Conversation, *, keep_question: bool) -> str:
    """Take back the latest turn, so it can be asked again.

    ``keep_question`` (regenerate) removes only the replies; the existing retry
    then answers the same message again. Without it (edit) the question goes
    too, and its text is returned for the person to change and resend.

    Only the latest turn: an earlier one has later turns built on it. Whatever
    that turn already saved (a fact, a plan, a follow-up) stays saved — it is
    on the Memory and Plans pages, where it can be removed.
    """
    messages = history(db, convo.id)
    last_user = next((m for m in reversed(messages) if m.role == "user"), None)
    if last_user is None:
        raise NothingToRewind("There is no message to take back.")
    replies = messages[messages.index(last_user) + 1 :]
    if not replies and keep_question:
        raise NothingToRewind("The latest message has no reply yet.")
    if any(r.pinned_at is not None for r in replies):
        # Taking it back would delete it from Saved replies without a word.
        raise NothingToRewind("That reply is saved. Remove it from Saved replies first.")
    for reply in replies:
        db.delete(reply)
    text = last_user.content
    if not keep_question:
        db.delete(last_user)
    # The summary never covers the latest turns, but keep the count honest.
    remaining = len(messages) - len(replies) - (0 if keep_question else 1)
    convo.summary_count = min(convo.summary_count or 0, remaining)
    db.flush()
    return text


def set_pinned(db: Session, user_id: str, message_id: str, pinned: bool) -> Message | None:
    msg = db.scalar(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.id == message_id,
            Conversation.user_id == user_id,
            Message.role == "assistant",
        )
    )
    if msg is None:
        return None
    msg.pinned_at = utcnow().replace(tzinfo=None) if pinned else None
    db.flush()
    return msg


def pinned(db: Session, user_id: str) -> list[tuple[Message, Conversation]]:
    """Saved replies, most recently saved first."""
    return list(
        db.execute(
            select(Message, Conversation)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id, Message.pinned_at.is_not(None))
            .order_by(Message.pinned_at.desc())
        ).all()
    )


def recent(db: Session, user_id: str, limit: int = 6) -> list[Conversation]:
    """The latest conversations across every agent, for the home page."""
    return list_conversations(db, user_id)[:limit]
