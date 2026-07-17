"""add page avatar

Revision ID: 0006_page_avatar
Revises: 0005_profile_avatar
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_page_avatar"
down_revision: str | None = "0005_profile_avatar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pages",
        sa.Column("avatar_media_asset_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "pages",
        sa.Column("avatar_media_owner_user_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pages", "avatar_media_owner_user_id")
    op.drop_column("pages", "avatar_media_asset_id")
