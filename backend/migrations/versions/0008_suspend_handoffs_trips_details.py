"""Account suspension, handoff note expiry, trip end dates, check-in details.

Revision ID: 0008
Revises: 0007

All nullable: existing accounts are active, existing notes are unseen, existing
follow-ups are single days, existing check-ins have no structured detail.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("suspended_at", sa.DateTime(), nullable=True))
    op.add_column("agent_memories", sa.Column("seen_at", sa.DateTime(), nullable=True))
    op.add_column("followups", sa.Column("ends_on", sa.Date(), nullable=True))
    op.add_column("checkins", sa.Column("details", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("checkins", "details")
    op.drop_column("followups", "ends_on")
    op.drop_column("agent_memories", "seen_at")
    op.drop_column("users", "suspended_at")
