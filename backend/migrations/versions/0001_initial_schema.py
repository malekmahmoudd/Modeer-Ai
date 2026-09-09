"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-09
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ts = dict(server_default=sa.func.now(), nullable=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), **_ts),
        sa.Column("updated_at", sa.DateTime(timezone=True), **_ts),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("display_name", sa.String(120), nullable=False, server_default="You"),
        sa.Column("onboarded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("profile", sa.JSON(), nullable=False, server_default="{}"),
        *_timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "agents",
        sa.Column("id", sa.String(48), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("accent", sa.String(24), nullable=False, server_default="#6366f1"),
        sa.Column("icon", sa.String(16), nullable=False, server_default="✨"),
        sa.Column("is_assistant", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(48), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default="New conversation"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_agent_id", "conversations", ["agent_id"])
    op.create_index(
        "ix_conversations_user_agent", "conversations", ["user_id", "agent_id"]
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", "created_at"]
    )

    op.create_table(
        "shared_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False, server_default="shared"),
        sa.Column("category", sa.String(48), nullable=False, server_default="general"),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source", sa.String(24), nullable=False, server_default="user"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("sensitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "key", name="uq_shared_memory_user_key"),
    )
    op.create_index("ix_shared_memories_user_id", "shared_memories", ["user_id"])
    op.create_index(
        "ix_shared_memories_user_category", "shared_memories", ["user_id", "category"]
    )

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(48), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False, server_default="agent"),
        sa.Column("category", sa.String(48), nullable=False, server_default="general"),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source", sa.String(24), nullable=False, server_default="agent"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("sensitive", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id", "agent_id", "key", name="uq_agent_memory_user_agent_key"
        ),
    )
    op.create_index("ix_agent_memories_user_id", "agent_memories", ["user_id"])
    op.create_index("ix_agent_memories_agent_id", "agent_memories", ["agent_id"])
    op.create_index(
        "ix_agent_memories_user_agent", "agent_memories", ["user_id", "agent_id"]
    )

    op.create_table(
        "goals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])
    op.create_index("ix_goals_user_status", "goals", ["user_id", "status"])

    op.create_table(
        "briefings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("generated_for_date", sa.String(10), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_briefings_user_id", "briefings", ["user_id"])
    op.create_index(
        "ix_briefings_user_created", "briefings", ["user_id", "created_at"]
    )


def downgrade() -> None:
    for table in (
        "briefings",
        "goals",
        "agent_memories",
        "shared_memories",
        "messages",
        "conversations",
        "agents",
        "users",
    ):
        op.drop_table(table)
