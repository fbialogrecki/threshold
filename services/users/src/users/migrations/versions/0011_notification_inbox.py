"""expand notification events into inbox

Revision ID: 0011_notification_inbox
Revises: 0010_safety_audit_log
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_notification_inbox"
down_revision: str | None = "0010_safety_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notification_events") as batch:
        batch.add_column(sa.Column("actor_user_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column(
                "target_type",
                sa.String(length=40),
                nullable=False,
                server_default="page",
            )
        )
        batch.add_column(
            sa.Column(
                "target_id",
                sa.String(length=150),
                nullable=False,
                server_default="unknown",
            )
        )
        batch.add_column(sa.Column("target_url", sa.String(length=300), nullable=True))
        batch.add_column(
            sa.Column(
                "title",
                sa.String(length=200),
                nullable=False,
                server_default="Notification",
            )
        )
        batch.add_column(sa.Column("body", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("dedupe_key", sa.String(length=200), nullable=True))
        batch.create_foreign_key(
            "fk_notification_events_actor_user_id",
            "application_users",
            ["actor_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_unique_constraint(
            "uq_notification_events_user_dedupe",
            ["user_id", "dedupe_key"],
        )
        batch.create_index(
            "ix_notification_events_user_read_created",
            ["user_id", "read_at", "created_at"],
        )


def downgrade() -> None:
    with op.batch_alter_table("notification_events") as batch:
        batch.drop_index("ix_notification_events_user_read_created")
        batch.drop_constraint("uq_notification_events_user_dedupe", type_="unique")
        batch.drop_constraint("fk_notification_events_actor_user_id", type_="foreignkey")
        batch.drop_column("dedupe_key")
        batch.drop_column("body")
        batch.drop_column("title")
        batch.drop_column("target_url")
        batch.drop_column("target_id")
        batch.drop_column("target_type")
        batch.drop_column("actor_user_id")
