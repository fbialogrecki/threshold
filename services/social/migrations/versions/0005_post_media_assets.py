"""add post media asset ids

Revision ID: 0005_post_media_assets
Revises: 0004_edited_at
Create Date: 2026-06-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_post_media_assets"
down_revision: str | None = "0004_edited_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("media_asset_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("posts", "media_asset_ids", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("posts") as batch_op:
        batch_op.drop_column("media_asset_ids")
