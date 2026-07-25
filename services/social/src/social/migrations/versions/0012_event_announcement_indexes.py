"""add event announcement lookup indexes

Revision ID: 0012_announcement_indexes
Revises: 0011_post_event_id
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012_announcement_indexes"
down_revision: str | None = "0011_post_event_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_event_announcements_post_id", table_name="event_announcements")
    op.create_index(
        "ix_event_announcements_post_created",
        "event_announcements",
        ["post_id", "created_at", "id"],
    )
    op.create_index(
        "ix_event_announcements_event_slug",
        "event_announcements",
        ["event_slug"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_announcements_event_slug", table_name="event_announcements")
    op.drop_index("ix_event_announcements_post_created", table_name="event_announcements")
    op.create_index("ix_event_announcements_post_id", "event_announcements", ["post_id"])
