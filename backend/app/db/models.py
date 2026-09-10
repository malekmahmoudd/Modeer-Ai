"""All ORM models for the Modeer modular monolith.

Kept in one module so relationships resolve without import cycles; each domain
package (users, conversations, memory, ...) owns the *behaviour* around them.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDMixin, new_uuid


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), default="You")
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)

    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    shared_memories: Mapped[list[SharedMemory]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    agent_memories: Mapped[list[AgentMemory]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    goals: Mapped[list[Goal]] = relationship(back_populates="user", cascade="all, delete-orphan")
    briefings: Mapped[list[Briefing]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Agent(TimestampMixin, Base):
    """Registry mirror. Source of truth is code (app/agents/<slug>/config.py);
    this table exists for FK integrity and future per-deployment overrides."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)  # slug
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    accent: Mapped[str] = mapped_column(String(24), default="#6366f1")
    icon: Mapped[str] = mapped_column(String(16), default="✨")
    is_assistant: Mapped[bool] = mapped_column(Boolean, default=False)  # Modeer
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    config_version: Mapped[int] = mapped_column(Integer, default=1)

    conversations: Mapped[list[Conversation]] = relationship(back_populates="agent")


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_agent", "user_id", "agent_id"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    last_message_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship(back_populates="conversations")
    agent: Mapped[Agent] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant" | "system"
    content: Mapped[str] = mapped_column(Text)
    # Diagnostics: which context was injected, token counts, model, etc.
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class SharedMemory(UUIDMixin, TimestampMixin, Base):
    """Personal context shared across the whole AI team."""

    __tablename__ = "shared_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_shared_memory_user_key"),
        Index("ix_shared_memories_user_category", "user_id", "category"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(16), default="shared")
    category: Mapped[str] = mapped_column(String(48), default="general")
    key: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(24), default="user")  # user|modeer|<agent>
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="shared_memories")


class AgentMemory(UUIDMixin, TimestampMixin, Base):
    """Memory private to one specialist (namespace = agent slug)."""

    __tablename__ = "agent_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_id", "key", name="uq_agent_memory_user_agent_key"),
        Index("ix_agent_memories_user_agent", "user_id", "agent_id"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(48), index=True)
    scope: Mapped[str] = mapped_column(String(16), default="agent")
    category: Mapped[str] = mapped_column(String(48), default="general")
    key: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(24), default="agent")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="agent_memories")


class Goal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (Index("ix_goals_user_status", "user_id", "status"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1 (top) .. 5
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|done|paused
    target_date: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship(back_populates="goals")


class Briefing(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "briefings"
    __table_args__ = (Index("ix_briefings_user_created", "user_id", "created_at"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    summary: Mapped[str] = mapped_column(Text)
    items: Mapped[list] = mapped_column(JSON, default=list)
    generated_for_date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD

    user: Mapped[User] = relationship(back_populates="briefings")


__all__ = [
    "new_uuid",
    "User",
    "Agent",
    "Conversation",
    "Message",
    "SharedMemory",
    "AgentMemory",
    "Goal",
    "Briefing",
    "UsageBucket",
]


class UsageBucket(Base):
    """Durable atomic counters; no prompts or credentials are stored."""

    __tablename__ = "usage_buckets"
    account: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
