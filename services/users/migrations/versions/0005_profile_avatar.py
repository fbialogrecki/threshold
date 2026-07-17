"""add profile avatar media asset id

Revision ID: 0005_profile_avatar
Revises: 0004_add_slice2_models
Create Date: 2026-06-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_profile_avatar"
down_revision: str | None = "0004_add_slice2_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "consumer_profiles",
        sa.Column("avatar_media_asset_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("consumer_profiles", "avatar_media_asset_id")
