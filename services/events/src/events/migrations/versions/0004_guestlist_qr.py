"""add guestlist qr check-in

Revision ID: 0004_guestlist_qr
Revises: 0003_event_updates
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_guestlist_qr"
down_revision: str | None = "0003_event_updates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_guestlist_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("guest_user_id", sa.String(length=36), nullable=False),
        sa.Column("guest_username", sa.String(length=150), nullable=True),
        sa.Column("guest_display_name", sa.String(length=160), nullable=False),
        sa.Column("added_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("added_by_artist_profile_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_in_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "guest_user_id", name="uq_event_guest_user"),
    )
    op.create_index(
        "ix_event_guestlist_guest_status",
        "event_guestlist_entries",
        ["guest_user_id", "status"],
    )
    op.create_index(
        "ix_event_guestlist_event_status",
        "event_guestlist_entries",
        ["event_id", "status"],
    )
    op.create_table(
        "event_guest_quotas",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("artist_profile_id", sa.String(length=36), nullable=False),
        sa.Column("quota", sa.Integer(), nullable=False),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "artist_profile_id", name="uq_event_artist_quota"),
    )
    op.create_table(
        "event_check_in_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("guestlist_entry_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["guestlist_entry_id"], ["event_guestlist_entries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_check_in_tokens_hash", "event_check_in_tokens", ["token_hash"])
    op.create_table(
        "event_access_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=150), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_event_access_audit_event_created",
        "event_access_audit_logs",
        ["event_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_event_access_audit_event_created", table_name="event_access_audit_logs")
    op.drop_table("event_access_audit_logs")
    op.drop_index("ix_check_in_tokens_hash", table_name="event_check_in_tokens")
    op.drop_table("event_check_in_tokens")
    op.drop_table("event_guest_quotas")
    op.drop_index("ix_event_guestlist_event_status", table_name="event_guestlist_entries")
    op.drop_index("ix_event_guestlist_guest_status", table_name="event_guestlist_entries")
    op.drop_table("event_guestlist_entries")
