"""add structured comment mentions

Revision ID: 0008_structured_mentions
Revises: 0007_safety_audit_log
Create Date: 2026-06-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_structured_mentions"
down_revision: str | None = "0007_safety_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("post_mentions") as batch:
        batch.add_column(sa.Column("target_id", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("display_name", sa.String(length=160), nullable=True))
        batch.add_column(sa.Column("target_url", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("start_index", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("end_index", sa.Integer(), nullable=True))

    op.create_table(
        "comment_mentions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("comment_id", sa.String(length=36), nullable=False),
        sa.Column("mention_type", sa.String(length=32), nullable=False),
        sa.Column("target_handle", sa.String(length=150), nullable=False),
        sa.Column("target_id", sa.String(length=150), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column("target_url", sa.String(length=300), nullable=True),
        sa.Column("start_index", sa.Integer(), nullable=True),
        sa.Column("end_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comment_mentions_comment_id", "comment_mentions", ["comment_id"])
    op.create_index(
        "ix_comment_mentions_target",
        "comment_mentions",
        ["mention_type", "target_handle"],
    )


def downgrade() -> None:
    op.drop_index("ix_comment_mentions_target", table_name="comment_mentions")
    op.drop_index("ix_comment_mentions_comment_id", table_name="comment_mentions")
    op.drop_table("comment_mentions")
    with op.batch_alter_table("post_mentions") as batch:
        batch.drop_column("end_index")
        batch.drop_column("start_index")
        batch.drop_column("target_url")
        batch.drop_column("display_name")
        batch.drop_column("target_id")
