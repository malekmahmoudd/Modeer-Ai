"""Reminders belong to a signed-in device; quick notes save once.

Revision ID: 0013
Revises: 0012

push_subscriptions gains session_id: signing that device out ends its
reminders. Existing subscriptions were made before this binding and cannot be
tied to a device, so they are removed; people turn reminders on again.

capture_receipts records each saved quick note by the browser's key, so a
retried save does not save it twice.
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DELETE FROM push_subscriptions")
    with op.batch_alter_table("push_subscriptions") as batch:
        batch.add_column(sa.Column("session_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_push_subscriptions_session_id", ["session_id"])
        batch.create_foreign_key(
            "fk_push_subscriptions_session_id",
            "user_sessions",
            ["session_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_table(
        "capture_receipts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "key", name="uq_capture_receipt_key"),
    )
    op.create_index("ix_capture_receipts_user_id", "capture_receipts", ["user_id"])


def downgrade():
    op.drop_index("ix_capture_receipts_user_id", table_name="capture_receipts")
    op.drop_table("capture_receipts")
    with op.batch_alter_table("push_subscriptions") as batch:
        batch.drop_constraint("fk_push_subscriptions_session_id", type_="foreignkey")
        batch.drop_index("ix_push_subscriptions_session_id")
        batch.drop_column("session_id")
