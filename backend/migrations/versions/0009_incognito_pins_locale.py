"""Incognito conversations, saved replies, interface language.

Revision ID: 0009
Revises: 0008

Existing conversations are ordinary, existing replies unsaved, and existing
accounts follow their browser's language.
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "conversations",
        sa.Column("incognito", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "conversations",
        sa.Column("incognito_context", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("conversations", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("messages", sa.Column("pinned_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("locale", sa.String(length=8), nullable=True))


def downgrade():
    op.drop_column("users", "locale")
    op.drop_column("messages", "pinned_at")
    op.drop_column("conversations", "expires_at")
    op.drop_column("conversations", "incognito_context")
    op.drop_column("conversations", "incognito")
