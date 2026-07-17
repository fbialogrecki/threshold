"""add feed candidate indexes

Revision ID: 0007_feed_indexes
Revises: 0006_one_issued_token
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_feed_indexes"
down_revision: str | None = "0006_one_issued_token"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_events_city_lower",
        "events",
        [sa.text("lower(city)")],
    )
    op.create_index(
        "ix_events_created_by_user_id",
        "events",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_events_created_cursor",
        "events",
        ["created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_events_created_cursor", table_name="events")
    op.drop_index("ix_events_created_by_user_id", table_name="events")
    op.drop_index("ix_events_city_lower", table_name="events")
