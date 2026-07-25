"""add slice2 models

Revision ID: 0004_add_slice2_models
Revises: 0003_product_auth
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_slice2_models"
down_revision: str | None = "0003_product_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create artist_profiles table
    op.create_table(
        "artist_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("links", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["application_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_artist_profiles_user_id"),
    )

    # 2. Create follows table
    op.create_table(
        "follows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("follower_user_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("target_handle", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["follower_user_id"], ["application_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "follower_user_id", "target_type", "target_id", name="uq_follows_follower_target"
        ),
    )

    # 3. Add columns to pages table
    with op.batch_alter_table("pages") as batch_op:
        batch_op.add_column(sa.Column("page_type", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("about", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("links", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("pages") as batch_op:
        batch_op.drop_column("links")
        batch_op.drop_column("about")
        batch_op.drop_column("city")
        batch_op.drop_column("page_type")

    op.drop_table("follows")
    op.drop_table("artist_profiles")
