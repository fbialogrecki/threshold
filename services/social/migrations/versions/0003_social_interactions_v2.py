"""social interactions v2: comment replies, up/down votes, emoji reactions

Revision ID: 0003_social_interactions_v2
Revises: 0002_add_post_mentions
Create Date: 2026-06-11

Upgrade:
- comments.parent_id (one level of nesting, enforced by the API layer),
- reactions.kind backfill 'like' -> 'up' (votes replace likes),
- comment_reactions table (one vote per user per comment),
- post_emoji_reactions table (one row per user per emoji per post).

Downgrade is lossy by design: 'up' votes are mapped back to 'like' and
'down' votes are deleted, because the pre-v2 schema has no concept of a
downvote. Comment votes and emoji reactions are dropped entirely.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_social_interactions_v2"
down_revision: str | None = "0002_add_post_mentions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("comments") as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_comments_parent_id",
            "comments",
            ["parent_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_comments_parent_id", ["parent_id"])

    op.execute("UPDATE reactions SET kind = 'up' WHERE kind = 'like'")

    op.create_table(
        "comment_reactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("comment_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comment_id", "user_id", name="uq_comment_reaction_comment_user"),
    )
    op.create_index("ix_comment_reactions_user_id", "comment_reactions", ["user_id"])

    op.create_table(
        "post_emoji_reactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        # String(32): ZWJ sequences (e.g. family emoji) exceed 16 characters.
        sa.Column("emoji", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "post_id", "user_id", "emoji", name="uq_post_emoji_reaction_post_user_emoji"
        ),
    )
    op.create_index("ix_post_emoji_reactions_user_id", "post_emoji_reactions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_post_emoji_reactions_user_id", table_name="post_emoji_reactions")
    op.drop_table("post_emoji_reactions")
    op.drop_index("ix_comment_reactions_user_id", table_name="comment_reactions")
    op.drop_table("comment_reactions")

    # Lossy: downvotes have no pre-v2 representation.
    op.execute("DELETE FROM reactions WHERE kind = 'down'")
    op.execute("UPDATE reactions SET kind = 'like' WHERE kind = 'up'")

    with op.batch_alter_table("comments") as batch_op:
        batch_op.drop_index("ix_comments_parent_id")
        batch_op.drop_constraint("fk_comments_parent_id", type_="foreignkey")
        batch_op.drop_column("parent_id")
