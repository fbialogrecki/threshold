"""add account erasure tombstones

Revision ID: 0002_erasure_tombstones
Revises: 0001_create_media_schema
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_erasure_tombstones"
down_revision: str | None = "0001_create_media_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_erasure_tombstones",
        sa.Column("owner_user_id", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("owner_user_id"),
    )


def downgrade() -> None:
    op.drop_table("account_erasure_tombstones")
