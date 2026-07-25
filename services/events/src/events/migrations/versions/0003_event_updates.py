"""add event updates

Revision ID: 0003_event_updates
Revises: 0002_location_mode
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_event_updates"
down_revision: str | None = "0002_location_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_updates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("author_user_id", sa.String(length=36), nullable=False),
        sa.Column("author_page_id", sa.String(length=36), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_event_updates_event_created", "event_updates", ["event_id", "created_at"]
    )
    op.create_index("ix_event_updates_created", "event_updates", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_event_updates_created", table_name="event_updates")
    op.drop_index("ix_event_updates_event_created", table_name="event_updates")
    op.drop_table("event_updates")
