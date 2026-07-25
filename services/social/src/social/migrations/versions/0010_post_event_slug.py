"""add post event slug

Revision ID: 0010_post_event_slug
Revises: 0009_event_announcements
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_post_event_slug"
down_revision: str | None = "0009_event_announcements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("event_slug", sa.String(length=160), nullable=True))
    op.execute(
        """
        UPDATE posts
        SET event_slug = (
            SELECT event_announcements.event_slug
            FROM event_announcements
            WHERE event_announcements.post_id = posts.id
            ORDER BY event_announcements.created_at, event_announcements.id
            LIMIT 1
        )
        WHERE event_slug IS NULL
          AND EXISTS (
              SELECT 1
              FROM event_announcements
              WHERE event_announcements.post_id = posts.id
          )
        """
    )
    op.create_index("ix_posts_event_slug", "posts", ["event_slug"])


def downgrade() -> None:
    op.drop_index("ix_posts_event_slug", table_name="posts")
    with op.batch_alter_table("posts") as batch_op:
        batch_op.drop_column("event_slug")
