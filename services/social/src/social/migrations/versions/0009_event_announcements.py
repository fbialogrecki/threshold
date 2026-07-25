"""add event announcements

Revision ID: 0009_event_announcements
Revises: 0008_structured_mentions
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_event_announcements"
down_revision: str | None = "0008_structured_mentions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_announcements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_slug", sa.String(length=160), nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("group_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_event_announcements_event_id"),
    )
    op.create_index("ix_event_announcements_post_id", "event_announcements", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_event_announcements_post_id", table_name="event_announcements")
    op.drop_table("event_announcements")
