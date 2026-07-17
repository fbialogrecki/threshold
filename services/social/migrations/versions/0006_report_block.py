"""report block moderation

Revision ID: 0006_report_block
Revises: 0005_post_media_assets
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_report_block"
down_revision: str | None = "0005_post_media_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("comments", sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "user_blocks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("blocker_user_id", sa.String(length=36), nullable=False),
        sa.Column("blocker_username", sa.String(length=150), nullable=True),
        sa.Column("blocked_user_id", sa.String(length=36), nullable=False),
        sa.Column("blocked_username", sa.String(length=150), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_user_blocks_pair"),
    )
    op.create_index("ix_user_blocks_blocked_user_id", "user_blocks", ["blocked_user_id"])
    op.create_table(
        "safety_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reporter_user_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_safety_reports_status_created", "safety_reports", ["status", "created_at"])
    op.create_index("ix_safety_reports_target", "safety_reports", ["target_type", "target_id"])


def downgrade() -> None:
    op.drop_index("ix_safety_reports_target", table_name="safety_reports")
    op.drop_index("ix_safety_reports_status_created", table_name="safety_reports")
    op.drop_table("safety_reports")
    op.drop_index("ix_user_blocks_blocked_user_id", table_name="user_blocks")
    op.drop_table("user_blocks")
    op.drop_column("comments", "hidden_at")
    op.drop_column("posts", "hidden_at")
