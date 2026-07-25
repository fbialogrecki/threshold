"""allow one issued check-in token per guest

Revision ID: 0006_one_issued_token
Revises: 0005_event_door_staff
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_one_issued_token"
down_revision: str | None = "0005_event_door_staff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_event_check_in_tokens_one_issued"
ISSUED = sa.text("status = 'issued'")


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                "LOCK TABLE event_check_in_tokens "
                "IN SHARE ROW EXCLUSIVE MODE"
            )
        )
    op.execute(
        sa.text(
            """
            UPDATE event_check_in_tokens
            SET status = 'revoked'
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT
                        id,
                        row_number() OVER (
                            PARTITION BY guestlist_entry_id
                            ORDER BY created_at DESC, id DESC
                        ) AS issued_rank
                    FROM event_check_in_tokens
                    WHERE status = 'issued'
                ) AS ranked
                WHERE issued_rank > 1
            )
            """
        )
    )
    op.create_index(
        INDEX_NAME,
        "event_check_in_tokens",
        ["guestlist_entry_id"],
        unique=True,
        postgresql_where=ISSUED,
        sqlite_where=ISSUED,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="event_check_in_tokens")
