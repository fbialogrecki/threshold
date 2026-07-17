"""add page residencies

Revision ID: 0013_page_residencies
Revises: 0012_notification_preferences
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_page_residencies"
down_revision: str | None = "0012_notification_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page_residencies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("page_id", sa.String(length=36), nullable=False),
        sa.Column("artist_user_id", sa.String(length=36), nullable=False),
        sa.Column("invited_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["artist_user_id"], ["application_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["application_users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id", "artist_user_id", name="uq_page_residency_page_artist"),
    )
    op.create_index(
        "ix_page_residencies_artist_status",
        "page_residencies",
        ["artist_user_id", "status"],
    )
    op.create_index(
        "ix_page_residencies_page_status",
        "page_residencies",
        ["page_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_page_residencies_page_status", table_name="page_residencies")
    op.drop_index("ix_page_residencies_artist_status", table_name="page_residencies")
    op.drop_table("page_residencies")
