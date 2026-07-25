"""add report and block safety tables

Revision ID: 0009_report_block
Revises: 0008_page_notifications
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_report_block"
down_revision: str | None = "0008_page_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_blocks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("blocker_user_id", sa.String(length=36), nullable=False),
        sa.Column("blocked_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["blocked_user_id"], ["application_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocker_user_id"], ["application_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_user_blocks_pair"),
    )
    op.create_index("ix_user_blocks_blocked_user_id", "user_blocks", ["blocked_user_id"])
    op.create_table(
        "content_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reporter_user_id", sa.String(length=36), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("target_handle", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"], ["application_users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_content_reports_target", "content_reports", ["target_type", "target_id"])
    op.create_index(
        "ix_content_reports_status_created", "content_reports", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_content_reports_status_created", table_name="content_reports")
    op.drop_index("ix_content_reports_target", table_name="content_reports")
    op.drop_table("content_reports")
    op.drop_index("ix_user_blocks_blocked_user_id", table_name="user_blocks")
    op.drop_table("user_blocks")
