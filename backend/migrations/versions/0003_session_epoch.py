"""Per-account session revocation.

Revision ID: 0003
Revises: 0002

Adds the session generation used to sign a person out of every device without
rotating the shared signing secret, which would sign out every account at once.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("session_epoch", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("users", "session_epoch")
