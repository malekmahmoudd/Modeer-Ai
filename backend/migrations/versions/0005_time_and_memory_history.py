"""User timezone and memory history.

Revision ID: 0005
Revises: 0004

Adds the timezone agents need to know what day it is for the person, and a
history of earlier values on each memory so an update never silently erases
what was there. All nullable: existing rows mean "zone not yet known" and
"no earlier values".
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("timezone", sa.String(length=64), nullable=True))
    op.add_column("shared_memories", sa.Column("history", sa.JSON(), nullable=True))
    op.add_column("agent_memories", sa.Column("history", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("agent_memories", "history")
    op.drop_column("shared_memories", "history")
    op.drop_column("users", "timezone")
