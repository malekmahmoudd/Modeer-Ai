"""Push reminders, prompt templates, CVs, organising chats, reply dialect.

Revision ID: 0012
Revises: 0011

New tables start empty. Existing chats are unpinned, unfiled and untagged;
existing accounts have no dialect set (teammates match how they write).
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def _stamps():
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _owner():
    return sa.Column(
        "user_id",
        sa.String(length=36),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade():
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _owner(),
        sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(length=200), nullable=False),
        sa.Column("auth", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=200), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(), nullable=True),
        *_stamps(),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    op.create_table(
        "push_sent",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _owner(),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        *_stamps(),
        sa.UniqueConstraint("user_id", "kind", "day", name="uq_push_sent_day"),
    )
    op.create_index("ix_push_sent_user_id", "push_sent", ["user_id"])
    op.create_table(
        "server_keys",
        sa.Column("name", sa.String(length=40), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _owner(),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.String(length=48), nullable=True),
        *_stamps(),
    )
    op.create_index("ix_prompt_templates_user_id", "prompt_templates", ["user_id"])
    op.create_table(
        "cv_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _owner(),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("target_role", sa.String(length=120), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        *_stamps(),
    )
    op.create_index("ix_cv_documents_user_id", "cv_documents", ["user_id"])
    op.add_column("conversations", sa.Column("pinned_at", sa.DateTime(), nullable=True))
    op.add_column("conversations", sa.Column("folder", sa.String(length=60), nullable=True))
    op.add_column("conversations", sa.Column("tags", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("reply_dialect", sa.String(length=16), nullable=True))


def downgrade():
    op.drop_column("users", "reply_dialect")
    op.drop_column("conversations", "tags")
    op.drop_column("conversations", "folder")
    op.drop_column("conversations", "pinned_at")
    op.drop_index("ix_cv_documents_user_id", table_name="cv_documents")
    op.drop_table("cv_documents")
    op.drop_index("ix_prompt_templates_user_id", table_name="prompt_templates")
    op.drop_table("prompt_templates")
    op.drop_table("server_keys")
    op.drop_index("ix_push_sent_user_id", table_name="push_sent")
    op.drop_table("push_sent")
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
