import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CurrentPrincipalRequest(BaseModel):
    authentik_subject: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    username: str | None = Field(default=None, max_length=150)


class ListFollowingRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)


class OnboardingPreferencesUpdate(BaseModel):
    city: str | None = Field(default=None, max_length=120)
    preferred_scenes: str | None = Field(default=None, max_length=2000)
    onboarding_skipped: bool = False


class ApplicationUserResponse(BaseModel):
    id: str
    authentik_subject: str | None
    email: str | None
    email_normalized: str | None = None
    email_verified: bool = False
    username: str | None
    username_normalized: str | None = None
    status: str = "active"
    identity_source: str = "product"

    model_config = ConfigDict(from_attributes=True)

    @field_validator("email_verified", mode="before")
    @classmethod
    def from_verified_at(_cls, value: object) -> bool:
        return bool(value)


class ConsumerProfileResponse(BaseModel):
    id: str
    display_name: str | None
    bio: str | None
    avatar_media_asset_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OnboardingPreferencesResponse(BaseModel):
    id: str
    city: str | None
    preferred_scenes: str | None
    onboarding_skipped: bool = False

    model_config = ConfigDict(from_attributes=True)


class ArtistProfileResponse(BaseModel):
    id: str
    role: str | None
    location: str | None
    links: list[dict[str, str]] = []

    model_config = ConfigDict(from_attributes=True)


class CurrentProfileResponse(BaseModel):
    user: ApplicationUserResponse
    consumer_profile: ConsumerProfileResponse
    onboarding_preferences: OnboardingPreferencesResponse
    artist_profile: ArtistProfileResponse | None = None


class UserProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    username: str | None = Field(default=None, max_length=30)
    bio: str | None = Field(default=None, max_length=2000)
    city: str | None = Field(default=None, max_length=120)
    avatar_media_asset_id: str | None = Field(default=None, max_length=36)

    @field_validator("username")
    @classmethod
    def username_policy(_cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", value):
            raise ValueError("invalid username")
        if value.strip("_.-").lower() in {"admin", "root", "support", "threshold"}:
            raise ValueError("reserved username")
        return value


class ArtistProfileUpdate(BaseModel):
    role: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    links: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("links")
    @classmethod
    def validate_links(_cls, links: list[dict[str, str]]) -> list[dict[str, str]]:
        for link in links:
            if "label" not in link or "url" not in link:
                raise ValueError("Each link must contain 'label' and 'url'")
            url = link["url"]
            if not (url.startswith("http://") or url.startswith("https://")):
                raise ValueError("URL must start with http:// or https://")
        return links


class FollowRequest(BaseModel):
    target_type: str = Field(..., description="artist|consumer|page")
    target_handle: str = Field(..., description="username or slug")

    @field_validator("target_type")
    @classmethod
    def validate_target_type(_cls, value: str) -> str:
        if value not in {
            "artist",
            "consumer",
            "page",
            "club",
            "collective",
            "project",
            "festival",
        }:
            raise ValueError("target_type must be artist, consumer or page")
        return value


class FollowedTargetResponse(BaseModel):
    target_type: str
    target_id: str
    target_handle: str
    display_name: str

    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=30)
    password: str = Field(min_length=1, max_length=1024)
    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def email_must_look_like_email(_cls, value: str) -> str:
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("invalid email")
        return value

    @field_validator("username")
    @classmethod
    def username_policy(_cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", value):
            raise ValueError("invalid username")
        if value.strip("_.-").lower() in {"admin", "root", "support", "threshold"}:
            raise ValueError("reserved username")
        return value


class RegisterResponse(CurrentProfileResponse):
    dev_email_verification_token: str | None = None


class LoginRequest(BaseModel):
    email_or_username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class TokenResponse(CurrentProfileResponse):
    pass


class EmailVerifyRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)


class EmailVerifyRequestResponse(BaseModel):
    status: str = "ok"
    dev_email_verification_token: str | None = None


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetRequestResponse(BaseModel):
    status: str = "ok"
    dev_password_reset_token: str | None = None


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)
    new_password: str = Field(min_length=1, max_length=1024)


class SimpleStatusResponse(BaseModel):
    status: str = "ok"


class PublicUserProfileResponse(BaseModel):
    id: str
    type: str  # "consumer" or "artist"
    username: str
    artist_profile_id: str | None = None
    display_name: str
    bio: str | None = None
    avatar_media_asset_id: str | None = None
    role: str | None = None
    location: str | None = None
    links: list[dict[str, str]] = []
    follower_count: int = 0
    residencies: list["PublicArtistResidencyResponse"] = []


class PublicArtistRefResponse(BaseModel):
    username: str
    display_name: str
    role: str | None = None
    target_url: str


class PublicArtistResidencyResponse(BaseModel):
    page_slug: str
    page_name: str
    page_type: str | None = None
    target_url: str


class PublicPageResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    page_type: str | None = None
    city: str | None = None
    about: str | None = None
    links: list[dict[str, str]] = []
    avatar_media_asset_id: str | None = None
    residents: list[PublicArtistRefResponse] = []
    follower_count: int = 0
    is_following: bool = False


class PublicPageRefResponse(BaseModel):
    slug: str
    display_name: str
    page_type: str | None = None
    target_url: str


PageId = Annotated[
    str,
    Field(
        strict=True,
        pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$",
    ),
]


class OrganizerRefsRequest(BaseModel):
    page_ids: list[PageId] = Field(max_length=100)

    model_config = ConfigDict(extra="forbid")


class OrganizerRefResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    page_type: str | None = None
    avatar_media_asset_id: str | None = None
    target_url: str


UserId = Annotated[str, Field(strict=True, min_length=1, max_length=36)]


class ActiveUserRefsRequest(BaseModel):
    user_ids: list[UserId] = Field(max_length=100)

    model_config = ConfigDict(extra="forbid")


class ActiveUserRefResponse(BaseModel):
    id: str
    username: str
    display_name: str


class ResidencyResponse(BaseModel):
    id: str
    status: str
    page: PublicPageRefResponse
    artist: PublicArtistRefResponse
    created_at: datetime
    updated_at: datetime
    responded_at: datetime | None = None


class PageCreateRequest(BaseModel):
    slug: str = Field(min_length=2, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    page_type: str = Field(description="club|collective|project|festival")
    city: str | None = Field(default=None, max_length=120)
    about: str | None = Field(default=None, max_length=2000)
    links: list[dict[str, str]] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def validate_slug(_cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9-]{2,120}", value):
            raise ValueError("slug must contain lowercase letters, numbers and hyphens only")
        return value

    @field_validator("page_type")
    @classmethod
    def validate_page_type(_cls, value: str) -> str:
        if value not in {"club", "collective", "project", "festival"}:
            raise ValueError("page_type must be one of club, collective, project, festival")
        return value

    @field_validator("links")
    @classmethod
    def validate_links(_cls, links: list[dict[str, str]]) -> list[dict[str, str]]:
        for link in links:
            if "label" not in link or "url" not in link:
                raise ValueError("Each link must contain 'label' and 'url'")
            url = link["url"]
            if not (url.startswith("http://") or url.startswith("https://")):
                raise ValueError("URL must start with http:// or https://")
        return links


class PageManagementResponse(PublicPageResponse):
    id: str
    role: str


class PageUpdateRequest(BaseModel):
    avatar_media_asset_id: str | None = Field(default=None, max_length=36)


class PageMembershipUpdateRequest(BaseModel):
    role: str = Field(description="admin|editor")

    @field_validator("role")
    @classmethod
    def validate_role(_cls, value: str) -> str:
        if value not in {"admin", "editor"}:
            raise ValueError("role must be admin or editor")
        return value


class PageMembershipResponse(BaseModel):
    role: str


class ReportCreateRequest(BaseModel):
    target_type: str = Field(description="profile|page|post|comment")
    target_handle: str = Field(min_length=1, max_length=150)
    reason: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("target_type")
    @classmethod
    def validate_target_type(_cls, value: str) -> str:
        if value not in {"profile", "page", "post", "comment"}:
            raise ValueError("target_type must be profile, page, post or comment")
        return value


class ReportResponse(BaseModel):
    id: str
    status: str
    reason: str
    target_type: str
    target_id: str
    target_handle: str
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BlockCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)


class BlockCheckResponse(BaseModel):
    blocked: bool


class SafetyAuditLogResponse(BaseModel):
    id: str
    actor_user_id: str | None = None
    action: str
    target_type: str
    target_id: str
    reason: str | None = None
    metadata_json: dict[str, str | int | bool | None] = Field(alias="metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class NotificationPreferenceUpdate(BaseModel):
    mentions_enabled: bool | None = None
    engagement_enabled: bool | None = None
    event_updates_enabled: bool | None = None
    page_updates_enabled: bool | None = None


class NotificationPreferenceResponse(BaseModel):
    mentions_enabled: bool
    engagement_enabled: bool
    event_updates_enabled: bool
    page_updates_enabled: bool


class MentionTargetResponse(BaseModel):
    target_type: str
    target_id: str
    handle: str
    display_name: str
    target_url: str
    recipient_user_id: str | None = None


class ArtistReferenceResponse(BaseModel):
    artist_profile_id: str
    user_id: str
    owner_user_id: str
    username: str
    display_name: str
    target_url: str


ArtistProfileId = Annotated[str, Field(strict=True, min_length=1, max_length=36)]


class ArtistReferencesRequest(BaseModel):
    artist_profile_ids: list[ArtistProfileId] = Field(max_length=100)

    model_config = ConfigDict(extra="forbid")


class NotificationCreateRequest(BaseModel):
    recipient_user_id: str = Field(min_length=1, max_length=36)
    actor_user_id: str | None = Field(default=None, max_length=36)
    type: str = Field(min_length=1, max_length=80)
    target_type: str = Field(min_length=1, max_length=40)
    target_id: str = Field(min_length=1, max_length=150)
    target_url: str | None = Field(default=None, max_length=300)
    title: str = Field(min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=500)
    dedupe_key: str | None = Field(default=None, max_length=200)
    metadata: dict[str, str | int | bool | None] = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    id: str
    recipient_user_id: str
    actor_user_id: str | None = None
    type: str
    target_type: str
    target_id: str
    target_url: str | None = None
    title: str
    body: str | None = None
    metadata: dict[str, str | int | bool | None]
    read_at: datetime | None = None
    created_at: datetime


class UnreadCountResponse(BaseModel):
    count: int


class SearchResultItem(BaseModel):
    type: str  # "consumer" | "artist" | "club" | "collective"
    handle: str
    display_name: str
    subtitle: str | None = None
