"""rename public location mode

Revision ID: 0002_location_mode
Revises: 0001_create_events_schema
Create Date: 2026-06-21
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002_location_mode"
down_revision: str | None = "0001_create_events_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE events SET location_mode = 'public_location' WHERE location_mode = 'public'")


def downgrade() -> None:
    op.execute("UPDATE events SET location_mode = 'public' WHERE location_mode = 'public_location'")
