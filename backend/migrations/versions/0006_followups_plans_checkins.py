"""Follow-ups, saved plans, check-ins, conversation summaries, memory provenance.

Revision ID: 0006
Revises: 0005

New tables for what the team now keeps track of between conversations, a
running summary on each conversation, and the message each learned fact came
from. Everything new is nullable or defaulted, so existing rows need nothing.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _timestamps():
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _user_fk():
    return sa.Column(
        "user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade():
    op.create_table(
        "followups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _user_fk(),
        sa.Column("agent_id", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("asked_at", sa.DateTime(), nullable=True),
        sa.Column("outcome", sa.String(length=200), nullable=True),
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_followups_user_id", "followups", ["user_id"])
    op.create_table(
        "plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _user_fk(),
        sa.Column("agent_id", sa.String(length=48), nullable=False),
        sa.Column(
            "goal_id", sa.String(length=36), sa.ForeignKey("goals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_plans_user_id", "plans", ["user_id"])
    op.create_table(
        "plan_steps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "plan_id", sa.String(length=36), sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("done_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_plan_steps_plan_id", "plan_steps", ["plan_id"])
    op.create_table(
        "checkins",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _user_fk(),
        sa.Column("agent_id", sa.String(length=48), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=24), nullable=True),
        sa.Column("logged_on", sa.Date(), nullable=False),
        sa.Column("source_message_id", sa.String(length=36), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_checkins_user_id", "checkins", ["user_id"])
    op.create_index("ix_checkins_user_agent_day", "checkins", ["user_id", "agent_id", "logged_on"])
    op.add_column("conversations", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("summary_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "shared_memories", sa.Column("source_message_id", sa.String(length=36), nullable=True)
    )
    op.add_column(
        "agent_memories", sa.Column("source_message_id", sa.String(length=36), nullable=True)
    )


def downgrade():
    op.drop_column("agent_memories", "source_message_id")
    op.drop_column("shared_memories", "source_message_id")
    op.drop_column("conversations", "summary_count")
    op.drop_column("conversations", "summary")
    op.drop_index("ix_checkins_user_agent_day", table_name="checkins")
    op.drop_index("ix_checkins_user_id", table_name="checkins")
    op.drop_table("checkins")
    op.drop_index("ix_plan_steps_plan_id", table_name="plan_steps")
    op.drop_table("plan_steps")
    op.drop_index("ix_plans_user_id", table_name="plans")
    op.drop_table("plans")
    op.drop_index("ix_followups_user_id", table_name="followups")
    op.drop_table("followups")
