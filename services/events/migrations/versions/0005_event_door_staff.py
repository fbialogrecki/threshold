"""add event door staff

Revision ID: 0005_event_door_staff
Revises: 0004_guestlist_qr
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_event_door_staff"
down_revision: str | None = "0004_guestlist_qr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_door_staff",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_door_staff_event_user"),
    )
    op.create_index("ix_event_door_staff_user", "event_door_staff", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_event_door_staff_user", table_name="event_door_staff")
    op.drop_table("event_door_staff")
