from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from events.db.base import Base
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class LocationMode(StrEnum):
    public_location = "public_location"
    tba = "tba"
    secret_location = "secret_location"


class GuestlistEntryStatus(StrEnum):
    active = "active"
    removed = "removed"


class CheckInStatus(StrEnum):
    issued = "issued"
    revoked = "revoked"
    used = "used"


class AccountErasureTombstone(Base):
    __tablename__ = "account_erasure_tombstones"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    erased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_page_starts", "page_id", "starts_at"),
        Index("ix_events_city_starts", "city", "starts_at"),
        Index("ix_events_starts", "starts_at"),
        Index("ix_events_city_lower", text("lower(city)")),
        Index("ix_events_created_by_user_id", "created_by_user_id"),
        Index("ix_events_created_cursor", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    location_mode: Mapped[str] = mapped_column(
        String(32), default=LocationMode.public_location.value, nullable=False
    )
    venue_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    genres: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    lineup: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list, nullable=False)
    page_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    poster_media_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventFollow(Base):
    __tablename__ = "event_follows"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_follow_event_user"),
        Index("ix_event_follows_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EventUpdate(Base):
    __tablename__ = "event_updates"
    __table_args__ = (
        Index("ix_event_updates_event_created", "event_id", "created_at"),
        Index("ix_event_updates_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    author_page_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="update", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventBoost(Base):
    __tablename__ = "event_boosts"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_boost_event_user"),
        Index("ix_event_boosts_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)



class EventGuestlistEntry(Base):
    __tablename__ = "event_guestlist_entries"
    __table_args__ = (
        UniqueConstraint("event_id", "guest_user_id", name="uq_event_guest_user"),
        Index("ix_event_guestlist_guest_status", "guest_user_id", "status"),
        Index("ix_event_guestlist_event_status", "event_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    guest_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    guest_username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    guest_display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    added_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    added_by_artist_profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=GuestlistEntryStatus.active.value, nullable=False
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventGuestQuota(Base):
    __tablename__ = "event_guest_quotas"
    __table_args__ = (
        UniqueConstraint("event_id", "artist_profile_id", name="uq_event_artist_quota"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    artist_profile_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quota: Mapped[int] = mapped_column(default=0, nullable=False)
    assigned_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventDoorStaff(Base):
    __tablename__ = "event_door_staff"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_door_staff_event_user"),
        Index("ix_event_door_staff_user", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    assigned_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class EventCheckInToken(Base):
    __tablename__ = "event_check_in_tokens"
    __table_args__ = (
        Index("ix_check_in_tokens_hash", "token_hash"),
        Index(
            "uq_event_check_in_tokens_one_issued",
            "guestlist_entry_id",
            unique=True,
            postgresql_where=text("status = 'issued'"),
            sqlite_where=text("status = 'issued'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    guestlist_entry_id: Mapped[str] = mapped_column(
        ForeignKey("event_guestlist_entries.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=CheckInStatus.issued.value, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EventAccessAuditLog(Base):
    __tablename__ = "event_access_audit_logs"
    __table_args__ = (Index("ix_event_access_audit_event_created", "event_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(150), nullable=False)
    metadata_json: Mapped[dict[str, str | int | bool | None]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
