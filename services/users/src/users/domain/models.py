from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from users.db.base import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class IdentitySource(StrEnum):
    product = "product"
    authentik_internal = "authentik_internal"


class UserStatus(StrEnum):
    active = "active"
    locked = "locked"
    erasure_pending = "erasure_pending"
    deleted = "deleted"


class PageMembershipRole(StrEnum):
    owner = "owner"
    admin = "admin"
    editor = "editor"


class ResidencyStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class UserBlock(Base):
    __tablename__ = "user_blocks"
    __table_args__ = (
        UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_user_blocks_pair"),
        Index("ix_user_blocks_blocked_user_id", "blocked_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    blocker_user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    blocked_user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ContentReport(Base):
    __tablename__ = "content_reports"
    __table_args__ = (
        Index("ix_content_reports_target", "target_type", "target_id"),
        Index("ix_content_reports_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reporter_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("application_users.id", ondelete="SET NULL"), nullable=True
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_handle: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class SafetyAuditLog(Base):
    __tablename__ = "safety_audit_logs"
    __table_args__ = (
        Index("ix_safety_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_safety_audit_logs_target", "target_type", "target_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("application_users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict[str, str | int | bool | None]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ApplicationUser(Base):
    __tablename__ = "application_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    authentik_subject: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_normalized: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    username: Mapped[str | None] = mapped_column(String(150), nullable=True)
    username_normalized: Mapped[str | None] = mapped_column(String(150), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=UserStatus.active.value, nullable=False)
    identity_source: Mapped[str] = mapped_column(
        String(32), default=IdentitySource.product.value, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    credential: Mapped["UserCredential | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    consumer_profile: Mapped["ConsumerProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    artist_profile: Mapped["ArtistProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    onboarding_preferences: Mapped["OnboardingPreferences | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    page_memberships: Mapped[list["PageMembership"]] = relationship(back_populates="user")
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")


class AccountErasureJob(Base):
    __tablename__ = "account_erasure_jobs"
    __table_args__ = (
        Index(
            "ix_account_erasure_jobs_due",
            "completed_at",
            "next_attempt_at",
            "lease_expires_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    current_stage: Mapped[str] = mapped_column(String(32), default="social", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    lease_owner: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserCredential(Base):
    __tablename__ = "user_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash_algorithm: Mapped[str] = mapped_column(
        String(32), default="argon2id", nullable=False
    )
    password_hash_params: Mapped[dict[str, int | str]] = mapped_column(JSON, nullable=False)
    pepper_version: Mapped[int] = mapped_column(Integer, nullable=False)
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped[ApplicationUser] = relationship(back_populates="credential")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    session_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    refresh_family_id: Mapped[str] = mapped_column(String(36), nullable=False)
    refresh_generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    user_agent_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user: Mapped[ApplicationUser] = relationship(back_populates="sessions")


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)


class AuthAuditLog(Base):
    __tablename__ = "auth_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("application_users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict[str, str | int | bool | None]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    mentions_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    engagement_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    event_updates_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    page_updates_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    __table_args__ = (
        Index("ix_notification_events_user_read_created", "user_id", "read_at", "created_at"),
        UniqueConstraint("user_id", "dedupe_key", name="uq_notification_events_user_dedupe"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("application_users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    target_id: Mapped[str] = mapped_column(String(150), nullable=False, default="unknown")
    target_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Notification")
    body: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict[str, str | int | bool | None]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ConsumerProfile(Base):
    __tablename__ = "consumer_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_media_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped[ApplicationUser] = relationship(back_populates="consumer_profile")


class OnboardingPreferences(Base):
    __tablename__ = "onboarding_preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_scenes: Mapped[str | None] = mapped_column(Text, nullable=True)
    onboarding_skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped[ApplicationUser] = relationship(back_populates="onboarding_preferences")


class ArtistProfile(Base):
    __tablename__ = "artist_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    links: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    user: Mapped[ApplicationUser] = relationship(back_populates="artist_profile")


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint(
            "follower_user_id", "target_type", "target_id", name="uq_follows_follower_target"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    follower_user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_handle: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    follower: Mapped[ApplicationUser] = relationship()


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    page_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    links: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list, nullable=False)
    avatar_media_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    avatar_media_owner_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    memberships: Mapped[list["PageMembership"]] = relationship(back_populates="page")


class PageResidency(Base):
    __tablename__ = "page_residencies"
    __table_args__ = (
        UniqueConstraint("page_id", "artist_user_id", name="uq_page_residency_page_artist"),
        Index("ix_page_residencies_artist_status", "artist_user_id", "status"),
        Index("ix_page_residencies_page_status", "page_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    artist_user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    invited_by_user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=ResidencyStatus.pending.value, nullable=False
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    page: Mapped[Page] = relationship()
    artist_user: Mapped[ApplicationUser] = relationship(foreign_keys=[artist_user_id])
    invited_by_user: Mapped[ApplicationUser] = relationship(foreign_keys=[invited_by_user_id])


class SecretLocationPayload(Base):
    __tablename__ = "secret_location_payloads"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "payload_version",
            name="uq_secret_location_event_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    area: Mapped[str | None] = mapped_column(String(160), nullable=True)
    encrypted_payload_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_payload_nonce: Mapped[str] = mapped_column(String(255), nullable=False)
    crypto_suite: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    key_envelopes: Mapped[list["SecretLocationKeyEnvelope"]] = relationship(
        back_populates="payload", cascade="all, delete-orphan"
    )


class SecretLocationKeyEnvelope(Base):
    __tablename__ = "secret_location_key_envelopes"
    __table_args__ = (
        UniqueConstraint(
            "payload_id",
            "recipient_user_id",
            "key_version",
            name="uq_secret_location_payload_recipient_key_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    payload_id: Mapped[str] = mapped_column(
        ForeignKey("secret_location_payloads.id", ondelete="CASCADE"), nullable=False
    )
    recipient_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    encrypted_payload_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    payload: Mapped[SecretLocationPayload] = relationship(back_populates="key_envelopes")


class PageMembership(Base):
    __tablename__ = "page_memberships"
    __table_args__ = (UniqueConstraint("page_id", "user_id", name="uq_page_membership_page_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("application_users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[PageMembershipRole] = mapped_column(
        Enum(PageMembershipRole, name="page_membership_role"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    page: Mapped[Page] = relationship(back_populates="memberships")
    user: Mapped[ApplicationUser] = relationship(back_populates="page_memberships")
