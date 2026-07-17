"""create events schema

Revision ID: 0001_create_events_schema
Revises:
Create Date: 2026-06-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_events_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("location_mode", sa.String(length=32), nullable=False),
        sa.Column("venue_name", sa.String(length=160), nullable=True),
        sa.Column("address", sa.String(length=400), nullable=True),
        sa.Column("genres", sa.JSON(), nullable=False),
        sa.Column("lineup", sa.JSON(), nullable=False),
        sa.Column("page_id", sa.String(length=36), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("poster_media_asset_id", sa.String(length=36), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_events_page_starts", "events", ["page_id", "starts_at"])
    op.create_index("ix_events_city_starts", "events", ["city", "starts_at"])
    op.create_index("ix_events_starts", "events", ["starts_at"])

    op.create_table(
        "event_follows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_follow_event_user"),
    )
    op.create_index("ix_event_follows_user_id", "event_follows", ["user_id"])

    op.create_table(
        "event_boosts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_boost_event_user"),
    )
    op.create_index("ix_event_boosts_user_id", "event_boosts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_event_boosts_user_id", table_name="event_boosts")
    op.drop_table("event_boosts")
    op.drop_index("ix_event_follows_user_id", table_name="event_follows")
    op.drop_table("event_follows")
    op.drop_index("ix_events_starts", table_name="events")
    op.drop_index("ix_events_city_starts", table_name="events")
    op.drop_index("ix_events_page_starts", table_name="events")
    op.drop_table("events")
