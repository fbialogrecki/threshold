"""add onboarding skipped flag

Revision ID: 0007_add_onboarding_skipped
Revises: 0006_page_avatar
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_onboarding_skipped"
down_revision: str | None = "0006_page_avatar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("onboarding_preferences") as batch_op:
        batch_op.add_column(
            sa.Column(
                "onboarding_skipped",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    with op.batch_alter_table("onboarding_preferences") as batch_op:
        batch_op.alter_column("onboarding_skipped", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("onboarding_preferences") as batch_op:
        batch_op.drop_column("onboarding_skipped")
