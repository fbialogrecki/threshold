"""create social schema

Revision ID: 0001_create_social_schema
Revises:
Create Date: 2026-06-08
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_social_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    created_at = datetime(2026, 6, 8, tzinfo=UTC)
    op.create_table(
        "groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("scene_tag", sa.String(length=80), nullable=True),
        sa.Column("official", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "group_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("group_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_membership_group_user"),
    )
    op.create_index("ix_group_memberships_user_id", "group_memberships", ["user_id"])
    op.create_table(
        "posts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("author_user_id", sa.String(length=36), nullable=False),
        sa.Column("author_username", sa.String(length=150), nullable=False),
        sa.Column("author_display_name", sa.String(length=160), nullable=False),
        sa.Column("author_type", sa.String(length=32), nullable=False),
        sa.Column("group_id", sa.String(length=36), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_posts_author_cursor", "posts", ["author_user_id", "created_at", "id"])
    op.create_index("ix_posts_cursor", "posts", ["created_at", "id"])
    op.create_index("ix_posts_group_cursor", "posts", ["group_id", "created_at", "id"])
    op.create_table(
        "comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("author_user_id", sa.String(length=36), nullable=False),
        sa.Column("author_username", sa.String(length=150), nullable=False),
        sa.Column("author_display_name", sa.String(length=160), nullable=False),
        sa.Column("author_type", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_post_cursor", "comments", ["post_id", "created_at", "id"])
    op.create_table(
        "reactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_reaction_post_user"),
    )

    groups = sa.table(
        "groups",
        sa.column("id", sa.String),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("city", sa.String),
        sa.column("scene_tag", sa.String),
        sa.column("official", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        groups,
        [
            {
                "id": "00000000-0000-0000-0000-000000000101",
                "slug": "techno-warsaw",
                "name": "Techno Warsaw",
                "city": "Warsaw",
                "scene_tag": "techno",
                "official": True,
                "created_at": created_at,
            },
            {
                "id": "00000000-0000-0000-0000-000000000102",
                "slug": "techno-wroclaw",
                "name": "Techno Wroclaw",
                "city": "Wroclaw",
                "scene_tag": "techno",
                "official": True,
                "created_at": created_at,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("reactions")
    op.drop_index("ix_comments_post_cursor", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_posts_group_cursor", table_name="posts")
    op.drop_index("ix_posts_cursor", table_name="posts")
    op.drop_index("ix_posts_author_cursor", table_name="posts")
    op.drop_table("posts")
    op.drop_index("ix_group_memberships_user_id", table_name="group_memberships")
    op.drop_table("group_memberships")
    op.drop_table("groups")
