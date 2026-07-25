"""add immutable post event references

Revision ID: 0011_post_event_id
Revises: 0010_post_event_slug
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_post_event_id"
down_revision: str | None = "0010_post_event_slug"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("event_id", sa.String(length=36), nullable=True))
    op.create_index("ix_posts_event_id", "posts", ["event_id"])
    op.execute(
        """
        UPDATE posts
        SET (event_id, event_slug) = (
            SELECT event_announcements.event_id, event_announcements.event_slug
            FROM event_announcements
            WHERE event_announcements.post_id = posts.id
            ORDER BY event_announcements.created_at, event_announcements.id
            LIMIT 1
        )
        WHERE EXISTS (
              SELECT 1
              FROM event_announcements
              WHERE event_announcements.post_id = posts.id
          )
        """
    )
    with op.batch_alter_table("posts") as batch_op:
        batch_op.create_check_constraint(
            "ck_posts_event_reference_pair",
            "(event_id IS NULL) = (event_slug IS NULL)",
        )
        batch_op.create_check_constraint(
            "ck_posts_image_or_event",
            "event_id IS NULL OR json_array_length(media_asset_ids) = 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("posts") as batch_op:
        batch_op.drop_constraint("ck_posts_image_or_event", type_="check")
        batch_op.drop_constraint("ck_posts_event_reference_pair", type_="check")
    op.drop_index("ix_posts_event_id", table_name="posts")
    with op.batch_alter_table("posts") as batch_op:
        batch_op.drop_column("event_id")
