"""User records, and the two rights a person has over them.

Modeer stores what someone tells it about their health, money, career and
routines. Anyone holding that has to be able to hand it back and to destroy it,
so :func:`export_user_data` and :func:`delete_user` are part of the product, not
an admin convenience.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentMemory,
    Briefing,
    Conversation,
    Goal,
    Message,
    SharedMemory,
    UsageBucket,
    User,
)
from app.users.schemas import ProfileUpdate

DEMO_EMAIL = "demo@modeer.local"


def get_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def get_or_create_demo_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(email=DEMO_EMAIL, display_name="You", onboarded=False)
        db.add(user)
        db.flush()
    return user


def update_profile(db: Session, user: User, data: ProfileUpdate) -> User:
    payload = data.model_dump(exclude_unset=True)
    if "profile" in payload and payload["profile"] is not None:
        merged = dict(user.profile or {})
        merged.update(payload.pop("profile"))
        user.profile = merged
    for field, value in payload.items():
        setattr(user, field, value)
    db.flush()
    return user


def export_user_data(db: Session, user: User) -> dict[str, Any]:
    """Everything stored about this person, in one JSON-serialisable document.

    Includes the full text of every message, because a transcript with the
    messages removed is not the user's data — it is a summary of it.
    """
    conversations = list(db.scalars(select(Conversation).where(Conversation.user_id == user.id)))
    messages_by_conversation: dict[str, list[Message]] = {}
    for conversation in conversations:
        messages_by_conversation[conversation.id] = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at)
            )
        )

    def when(value) -> str | None:
        return value.isoformat() if value else None

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "format": "modeer-export-1",
        "account": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "onboarded": user.onboarded,
            "profile": user.profile or {},
            "created_at": when(user.created_at),
        },
        "conversations": [
            {
                "id": c.id,
                "agent_id": c.agent_id,
                "title": c.title,
                "last_message_at": when(c.last_message_at),
                "created_at": when(c.created_at),
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "created_at": when(m.created_at),
                    }
                    for m in messages_by_conversation[c.id]
                ],
            }
            for c in conversations
        ],
        "shared_memories": [
            {
                "id": m.id,
                "category": m.category,
                "key": m.key,
                "value": m.value,
                "confidence": m.confidence,
                "source": m.source,
                "sensitive": m.sensitive,
                "pinned": m.pinned,
                "created_at": when(m.created_at),
            }
            for m in db.scalars(select(SharedMemory).where(SharedMemory.user_id == user.id))
        ],
        "agent_memories": [
            {
                "id": m.id,
                "agent_id": m.agent_id,
                "category": m.category,
                "key": m.key,
                "value": m.value,
                "confidence": m.confidence,
                "source": m.source,
                "sensitive": m.sensitive,
                "created_at": when(m.created_at),
            }
            for m in db.scalars(select(AgentMemory).where(AgentMemory.user_id == user.id))
        ],
        "goals": [
            {
                "id": g.id,
                "title": g.title,
                "detail": g.detail,
                "status": g.status,
                "priority": g.priority,
                "target_date": when(g.target_date),
                "created_at": when(g.created_at),
            }
            for g in db.scalars(select(Goal).where(Goal.user_id == user.id))
        ],
        "briefings": [
            {
                "id": b.id,
                "summary": b.summary,
                "items": b.items,
                "generated_for_date": when(b.generated_for_date),
                "created_at": when(b.created_at),
            }
            for b in db.scalars(select(Briefing).where(Briefing.user_id == user.id))
        ],
    }


def delete_user(db: Session, user: User) -> None:
    """Erase the account and everything belonging to it.

    Conversations, memories, goals and briefings cascade from the user row. The
    usage ledger does not — it is keyed by account id with no foreign key, so it
    would survive the deletion and keep a record of when this person used the
    product. It is removed explicitly.
    """
    db.execute(delete(UsageBucket).where(UsageBucket.account == user.id))
    db.delete(user)
    db.flush()
