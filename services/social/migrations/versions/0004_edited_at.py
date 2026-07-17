"""owner edit support: edited_at timestamps on posts and comments

Revision ID: 0004_edited_at
Revises: 0003_social_interactions_v2
Create Date: 2026-06-12

Nullable edited_at marks owner edits; NULL means never edited.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_edited_at"
down_revision: str | None = "0003_social_interactions_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("comments", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("comments", "edited_at")
    op.drop_column("posts", "edited_at")
