"""add post mentions

Revision ID: 0002_add_post_mentions
Revises: 0001_create_social_schema
Create Date: 2026-06-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_post_mentions"
down_revision: str | None = "0001_create_social_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "post_mentions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("mention_type", sa.String(length=32), nullable=False),
        sa.Column("target_handle", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_post_mentions_post_id", "post_mentions", ["post_id"])
    op.create_index(
        "ix_post_mentions_target",
        "post_mentions",
        ["mention_type", "target_handle"],
    )


def downgrade() -> None:
    op.drop_index("ix_post_mentions_target", table_name="post_mentions")
    op.drop_index("ix_post_mentions_post_id", table_name="post_mentions")
    op.drop_table("post_mentions")
