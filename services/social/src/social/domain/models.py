from datetime import UTC, datetime
from uuid import uuid4

from social.db.base import Base
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    scene_tag: Mapped[str | None] = mapped_column(String(80), nullable=True)
    official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    memberships: Mapped[list["GroupMembership"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    posts: Mapped[list["Post"]] = relationship(back_populates="group")


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_membership_group_user"),
        Index("ix_group_memberships_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    group: Mapped[Group] = relationship(back_populates="memberships")


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_group_cursor", "group_id", "created_at", "id"),
        Index("ix_posts_author_cursor", "author_user_id", "created_at", "id"),
        Index("ix_posts_cursor", "created_at", "id"),
        Index("ix_posts_event_id", "event_id"),
        Index("ix_posts_event_slug", "event_slug"),
        CheckConstraint(
            "(event_id IS NULL) = (event_slug IS NULL)",
            name="ck_posts_event_reference_pair",
        ),
        CheckConstraint(
            "event_id IS NULL OR json_array_length(media_asset_ids) = 0",
            name="ck_posts_image_or_event",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    author_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    author_username: Mapped[str] = mapped_column(String(150), nullable=False)
    author_display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    author_type: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    group_id: Mapped[str | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"), nullable=True
    )
    event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_slug: Mapped[str | None] = mapped_column(String(160), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    media_asset_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group: Mapped[Group | None] = relationship(back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    mentions: Mapped[list["PostMention"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )


class EventAnnouncement(Base):
    __tablename__ = "event_announcements"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_event_announcements_event_id"),
        Index("ix_event_announcements_event_slug", "event_slug"),
        Index("ix_event_announcements_post_created", "post_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_slug: Mapped[str] = mapped_column(String(160), nullable=False)
    post_id: Mapped[str] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[str] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PostMention(Base):
    __tablename__ = "post_mentions"
    __table_args__ = (
        Index("ix_post_mentions_post_id", "post_id"),
        Index("ix_post_mentions_target", "mention_type", "target_handle"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    mention_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_handle: Mapped[str] = mapped_column(String(150), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    target_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    start_index: Mapped[int | None] = mapped_column(nullable=True)
    end_index: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    post: Mapped[Post] = relationship(back_populates="mentions")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_post_cursor", "post_id", "created_at", "id"),
        Index("ix_comments_parent_id", "parent_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    # Up to two levels of nesting: comment -> reply -> reply-to-reply (API-enforced).
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE", name="fk_comments_parent_id"),
        nullable=True,
    )
    author_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    author_username: Mapped[str] = mapped_column(String(150), nullable=False)
    author_display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    author_type: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    post: Mapped[Post] = relationship(back_populates="comments")
    reactions: Mapped[list["CommentReaction"]] = relationship(
        back_populates="comment", cascade="all, delete-orphan"
    )
    mentions: Mapped[list["CommentMention"]] = relationship(
        back_populates="comment", cascade="all, delete-orphan"
    )


class CommentMention(Base):
    __tablename__ = "comment_mentions"
    __table_args__ = (
        Index("ix_comment_mentions_comment_id", "comment_id"),
        Index("ix_comment_mentions_target", "mention_type", "target_handle"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    comment_id: Mapped[str] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=False
    )
    mention_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_handle: Mapped[str] = mapped_column(String(150), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    target_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    start_index: Mapped[int | None] = mapped_column(nullable=True)
    end_index: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    comment: Mapped[Comment] = relationship(back_populates="mentions")


class Reaction(Base):
    """Post vote: kind is 'up' or 'down', one row per user per post."""

    __tablename__ = "reactions"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_reaction_post_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="up", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    post: Mapped[Post] = relationship(back_populates="reactions")


class CommentReaction(Base):
    """Comment vote: kind is 'up' or 'down', one row per user per comment."""

    __tablename__ = "comment_reactions"
    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_reaction_comment_user"),
        Index("ix_comment_reactions_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    comment_id: Mapped[str] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    comment: Mapped[Comment] = relationship(back_populates="reactions")


class UserBlock(Base):
    __tablename__ = "user_blocks"
    __table_args__ = (
        UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_user_blocks_pair"),
        Index("ix_user_blocks_blocked_user_id", "blocked_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    blocker_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    blocker_username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    blocked_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    blocked_username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SafetyReport(Base):
    __tablename__ = "safety_reports"
    __table_args__ = (
        Index("ix_safety_reports_status_created", "status", "created_at"),
        Index("ix_safety_reports_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reporter_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SafetyAuditLog(Base):
    __tablename__ = "safety_audit_logs"
    __table_args__ = (
        Index("ix_safety_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_safety_audit_logs_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict[str, str | int | bool | None]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PostEmojiReaction(Base):
    """Emoji reaction on a post, independent of votes; one row per user per emoji."""

    __tablename__ = "post_emoji_reactions"
    __table_args__ = (
        UniqueConstraint(
            "post_id", "user_id", "emoji", name="uq_post_emoji_reaction_post_user_emoji"
        ),
        Index("ix_post_emoji_reactions_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # String(32): ZWJ sequences (e.g. family emoji) exceed 16 characters.
    emoji: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
