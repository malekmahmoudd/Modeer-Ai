"""All ORM models for the Modeer modular monolith.

Kept in one module so relationships resolve without import cycles; each domain
package (users, conversations, memory, ...) owns the *behaviour* around them.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
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
    #: Session generation. Bumping it invalidates this account's cookies
    #: everywhere without touching anyone else's — the shared signing secret
    #: cannot do that, since rotating it signs out every account at once.
    session_epoch: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    #: scrypt hash (app.core.passwords). None for accounts that sign in with an
    #: operator-issued access key and have not set a password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    #: Whether Modeer may learn facts from this person's messages automatically.
    #: Their own saves and edits on the Memory page are unaffected.
    memory_auto: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="1"
    )
    #: IANA timezone the browser reported ("Europe/London"). None until known;
    #: agents then work in UTC. See app/core/clock.py.
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Set by an operator to stop an account from signing in or using the API.
    #: Reversible; nothing is deleted.
    suspended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    #: Interface language: "en" or "ar". None follows the browser.
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)
    #: Two-step sign-in with an authenticator app (RFC 6238). The base32 secret
    #: is stored as is: like everything else here, the operator can read it, and
    #: backups are encrypted. ``totp_pending`` holds a secret being set up, not
    #: yet confirmed with a code; ``totp_last_step`` stops a code being reused.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_pending: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    totp_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)

    recovery_codes: Mapped[list[RecoveryCode]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[UserSession]] = relationship(cascade="all, delete-orphan")
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
    followups: Mapped[list[FollowUp]] = relationship(cascade="all, delete-orphan")
    plans: Mapped[list[Plan]] = relationship(cascade="all, delete-orphan")
    checkins: Mapped[list[CheckIn]] = relationship(cascade="all, delete-orphan")
    documents: Mapped[list[Document]] = relationship(cascade="all, delete-orphan")
    briefings: Mapped[list[Briefing]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(UUIDMixin, TimestampMixin, Base):
    """One signed-in device. Its id travels in the session cookie, so one device
    can be signed out without touching the others.

    Only what the Account page shows is kept: the browser's own description of
    itself and the first part of the network address (never the whole address).
    Rows are removed 30 days after they end.
    """

    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    #: The account's session generation when this began; a later "sign out
    #: everywhere" or password change ends it.
    epoch: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: password | key | signup | recovery | refresh
    method: Mapped[str] = mapped_column(String(16), default="password")
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ip_prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime] = mapped_column()
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)


class RecoveryCode(UUIDMixin, TimestampMixin, Base):
    """One single-use way back into an account whose password was lost.

    Only a hash is kept. A code is spent by setting ``used_at``, not deleted, so
    the Account page can say how many remain.
    """

    __tablename__ = "recovery_codes"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship(back_populates="recovery_codes")


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
    #: A running summary of the turns too old to send with each message, and how
    #: many of the model-visible messages it covers (from the start).
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    #: Incognito: nothing is learned from it, it is hidden from lists and from
    #: Leo, and it is deleted at ``expires_at`` (or when the person closes it).
    incognito: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="0"
    )
    #: An incognito chat sends no saved context unless the person opts in.
    incognito_context: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="0"
    )
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship(back_populates="conversations")
    agent: Mapped[Agent] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        # Same order as conversations.service.history: the id is only a
        # tie-break for rows written before timestamps were kept distinct.
        order_by="Message.created_at, Message.id",
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
    #: Kept by the person ("Saved replies"). Goes when the conversation does.
    pinned_at: Mapped[datetime | None] = mapped_column(nullable=True)

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
    #: Earlier values, newest last: [{"value", "source", "replaced_at"}]. An
    #: update never silently erases what was there.
    history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    #: The user message this fact was learned from (None when saved by hand).
    source_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

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
    history: Mapped[list | None] = mapped_column(JSON, nullable=True)  # as SharedMemory
    source_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    #: Handoff notes only: when the teammate first had it in front of them. Notes
    #: expire a while after that, so a stale brief stops steering the agent.
    seen_at: Mapped[datetime | None] = mapped_column(nullable=True)

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


class FollowUp(UUIDMixin, TimestampMixin, Base):
    """A dated thing the person mentioned: an interview, an exam, a trip.

    Shown counting down in the briefing and to the agents; once the day has
    passed, the agent who owns it asks how it went, once.
    """

    __tablename__ = "followups"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(48))  # the teammate it belongs with
    title: Mapped[str] = mapped_column(String(200))
    due_on: Mapped[date] = mapped_column(Date)
    #: Last day, for things that span days (a trip). "How did it go?" waits for it.
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|done|dismissed
    #: When an agent was first prompted to ask how it went. Asked once, not nagged.
    asked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    #: How it went, in the user's words, once they said so. Closes the follow-up.
    outcome: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Plan(UUIDMixin, TimestampMixin, Base):
    """A plan an agent wrote that the person chose to keep, as a checklist."""

    __tablename__ = "plans"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(48))
    goal_id: Mapped[str | None] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|done|archived
    starts_on: Mapped[date] = mapped_column(Date)
    source_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    steps: Mapped[list[PlanStep]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanStep.position"
    )


class PlanStep(UUIDMixin, Base):
    __tablename__ = "plan_steps"

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="steps")


class CheckIn(UUIDMixin, TimestampMixin, Base):
    """Progress the person reported: a workout, a study session, spending."""

    __tablename__ = "checkins"
    __table_args__ = (Index("ix_checkins_user_agent_day", "user_id", "agent_id", "logged_on"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(48))
    text: Mapped[str] = mapped_column(String(300))
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(24), nullable=True)
    #: Structured detail when there is some: a lift ({"exercise", "sets", "reps",
    #: "load", "load_unit", "rpe"}), a run ({"distance_km", "duration_min"}), or
    #: money ({"direction": "out"|"in", "currency"}). Validated on the way in.
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    logged_on: Mapped[date] = mapped_column(Date)
    source_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Document(UUIDMixin, TimestampMixin, Base):
    """A file the person gave one of their agents, kept as extracted text only.

    The uploaded bytes are parsed and then discarded: what is stored is the text
    the agents can quote, split into chunks. Nothing binary is kept or backed up.
    """

    __tablename__ = "documents"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    #: The agent it was given to. Only that agent retrieves from it, unless shared.
    agent_id: Mapped[str] = mapped_column(String(48))
    shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: Display name only, cleaned of control characters; never used as a path.
    filename: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(8))  # pdf | docx | txt | md | image
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="processing")  # processing|ready|failed
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    chars: Mapped[int] = mapped_column(Integer, default=0)
    #: The embedding model the chunks were embedded with; None = keyword search only.
    embed_model: Mapped[str | None] = mapped_column(String(80), nullable=True)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.position"
    )


class DocumentChunk(UUIDMixin, Base):
    __tablename__ = "document_chunks"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading: Mapped[str | None] = mapped_column(String(200), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    #: float32 vector, L2-normalised, as raw bytes. None when embeddings are off.
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")


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
    "FollowUp",
    "Plan",
    "PlanStep",
    "CheckIn",
    "Document",
    "DocumentChunk",
    "UsageBucket",
]


class UsageBucket(Base):
    """Durable atomic counters; no prompts or credentials are stored."""

    __tablename__ = "usage_buckets"
    account: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
