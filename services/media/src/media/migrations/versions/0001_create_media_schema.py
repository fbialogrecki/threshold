"""create media schema

Revision ID: 0001_create_media_schema
Revises:
Create Date: 2026-06-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_media_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("context", sa.String(length=32), nullable=False),
        sa.Column("bucket", sa.String(length=160), nullable=False),
        sa.Column("original_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket", "original_key", name="uq_media_assets_bucket_original_key"),
    )
    op.create_index(
        "ix_media_assets_context_created", "media_assets", ["context", "created_at"]
    )
    op.create_index(
        "ix_media_assets_owner_context",
        "media_assets",
        ["owner_user_id", "context", "created_at"],
    )
    op.create_table(
        "media_derivatives",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("variant", sa.String(length=64), nullable=False),
        sa.Column("bucket", sa.String(length=160), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("width", sa.BigInteger(), nullable=True),
        sa.Column("height", sa.BigInteger(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["media_assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "variant", name="uq_media_derivatives_asset_variant"),
        sa.UniqueConstraint("bucket", "object_key", name="uq_media_derivatives_bucket_object_key"),
    )


def downgrade() -> None:
    op.drop_table("media_derivatives")
    op.drop_index("ix_media_assets_owner_context", table_name="media_assets")
    op.drop_index("ix_media_assets_context_created", table_name="media_assets")
    op.drop_table("media_assets")
