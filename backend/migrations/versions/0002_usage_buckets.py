"""Durable account usage limits.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usage_buckets",
        sa.Column("account", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(16), primary_key=True),
        sa.Column("window", sa.Integer(), primary_key=True),
        sa.Column("amount", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("usage_buckets")
