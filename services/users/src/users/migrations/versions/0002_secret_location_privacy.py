"""add secret location encrypted payload tables

Revision ID: 0002_secret_location_privacy
Revises: 0001_create_users_schema
Create Date: 2026-05-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_secret_location_privacy"
down_revision: str | None = "0001_create_users_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "secret_location_payloads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("area", sa.String(length=160), nullable=True),
        sa.Column("encrypted_payload_ciphertext", sa.Text(), nullable=False),
        sa.Column("encrypted_payload_nonce", sa.String(length=255), nullable=False),
        sa.Column("crypto_suite", sa.String(length=120), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "payload_version",
            name="uq_secret_location_event_version",
        ),
    )
    op.create_table(
        "secret_location_key_envelopes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("payload_id", sa.String(length=36), nullable=False),
        sa.Column("recipient_user_id", sa.String(length=36), nullable=False),
        sa.Column("encrypted_payload_key", sa.Text(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["payload_id"],
            ["secret_location_payloads.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payload_id",
            "recipient_user_id",
            "key_version",
            name="uq_secret_location_payload_recipient_key_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("secret_location_key_envelopes")
    op.drop_table("secret_location_payloads")
