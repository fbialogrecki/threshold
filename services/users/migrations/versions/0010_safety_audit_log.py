"""add safety audit log

Revision ID: 0010_safety_audit_log
Revises: 0009_report_block
Create Date: 2026-06-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_safety_audit_log"
down_revision: str | None = "0009_report_block"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "safety_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["application_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_safety_audit_logs_actor_created",
        "safety_audit_logs",
        ["actor_user_id", "created_at"],
    )
    op.create_index(
        "ix_safety_audit_logs_target",
        "safety_audit_logs",
        ["target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_safety_audit_logs_target", table_name="safety_audit_logs")
    op.drop_index("ix_safety_audit_logs_actor_created", table_name="safety_audit_logs")
    op.drop_table("safety_audit_logs")
