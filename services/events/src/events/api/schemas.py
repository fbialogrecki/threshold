import re
from datetime import datetime
from typing import Annotated, Literal

from events.domain.models import GuestlistEntryStatus, LocationMode
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_genres(value: list[str]) -> list[str]:
    if any(len(genre) > 40 for genre in value):
        raise ValueError("genre must be at most 40 characters")
    return value


def _validate_lineup(value: list[dict[str, str]]) -> list[dict[str, str]]:
    for item in value:
        name = item.get("name", "").strip()
        if not name:
            raise ValueError("lineup item must include name")
        if len(name) > 160:
            raise ValueError("lineup item name must be at most 160 characters")
        artist_profile_id = item.get("artist_profile_id")
        if artist_profile_id is not None and len(artist_profile_id) > 36:
            raise ValueError("lineup item artist_profile_id must be at most 36 characters")
    return value


class EventCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=3, max_length=160)
    starts_at: datetime
    city: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    genres: list[str] = Field(default_factory=list, max_length=10)
    poster_media_asset_id: str | None = Field(default=None, max_length=36)
    page_id: str = Field(min_length=36, max_length=36)
    location_mode: LocationMode = LocationMode.public_location
    venue_name: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=400)
    lineup: list[dict[str, str]] = Field(default_factory=list, max_length=100)

    @field_validator("location_mode", mode="before")
    @classmethod
    def normalize_location_mode(_cls, v: object) -> object:
        return LocationMode.public_location if v == "public" else v

    @field_validator("slug")
    @classmethod
    def normalize_slug(_cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("slug must contain only lowercase letters, digits, and hyphens")
        return v

    @field_validator("genres")
    @classmethod
    def validate_genres(_cls, v: list[str]) -> list[str]:
        return _validate_genres(v)

    @field_validator("lineup")
    @classmethod
    def validate_lineup(_cls, v: list[dict[str, str]]) -> list[dict[str, str]]:
        return _validate_lineup(v)


class EventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    starts_at: datetime | None = None
    city: str | None = Field(default=None, min_length=1, max_length=120)
    genres: list[str] | None = Field(default=None, max_length=10)
    poster_media_asset_id: str | None = Field(default=None, max_length=36)
    location_mode: LocationMode | None = None
    venue_name: str | None = Field(default=None, max_length=160)
    address: str | None = Field(default=None, max_length=400)
    lineup: list[dict[str, str]] | None = Field(default=None, max_length=100)

    @field_validator("location_mode", mode="before")
    @classmethod
    def normalize_location_mode(_cls, v: object) -> object:
        return LocationMode.public_location if v == "public" else v

    @field_validator("genres")
    @classmethod
    def validate_genres(_cls, v: list[str] | None) -> list[str] | None:
        return _validate_genres(v) if v is not None else None

    @field_validator("lineup")
    @classmethod
    def validate_lineup(_cls, v: list[dict[str, str]] | None) -> list[dict[str, str]] | None:
        return _validate_lineup(v) if v is not None else None


class EventResponse(BaseModel):
    id: str
    slug: str
    title: str
    description: str | None
    starts_at: datetime
    city: str
    location_mode: str
    venue_name: str | None
    address: str | None
    genres: list[str]
    lineup: list[dict[str, str]]
    page_id: str
    poster_media_asset_id: str | None
    created_by_user_id: str
    boost_count: int
    follower_count: int
    is_following: bool | None = None
    is_boosting: bool | None = None
    created_at: datetime
    updated_at: datetime


EventSlug = Annotated[
    str,
    Field(strict=True, min_length=3, max_length=160, pattern=r"^[a-z0-9-]+$"),
]


class EventBatchRequest(BaseModel):
    slugs: list[EventSlug] = Field(max_length=100)

    model_config = ConfigDict(extra="forbid")


class AccountErasureRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=150)
    artist_profile_ids: list[str] = Field(default_factory=list, max_length=10)

    model_config = ConfigDict(extra="forbid")


class AccountErasureResponse(BaseModel):
    status: Literal["ok"] = "ok"


EventId = Annotated[str, Field(strict=True, min_length=1, max_length=36)]


class EventFeedCandidatesRequest(BaseModel):
    city: str | None = Field(default=None, min_length=1, max_length=120)
    followed_page_ids: list[EventId] = Field(default_factory=list, max_length=100)
    followed_creator_user_ids: list[EventId] = Field(default_factory=list, max_length=100)
    limit: int = Field(default=100, ge=1, le=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("city")
    @classmethod
    def strip_city(_cls, value: str | None) -> str | None:
        if value is None:
            return None
        city = value.strip()
        if not city:
            raise ValueError("city must not be blank")
        return city


class EventUpdateCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def validate_body(_cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body must not be blank")
        if "<" in stripped or ">" in stripped:
            raise ValueError("body must not contain HTML")
        return stripped


class EventUpdateResponse(BaseModel):
    id: str
    event_id: str
    event_slug: str
    event_title: str
    author_user_id: str
    author_page_id: str
    body: str
    kind: str
    created_at: datetime
    updated_at: datetime


class EventUpdateListResponse(BaseModel):
    items: list[EventUpdateResponse]
    next_before: str | None = None



class GuestlistAddRequest(BaseModel):
    guest_user_id: str | None = Field(default=None, min_length=1, max_length=36)
    guest_display_name: str | None = Field(default=None, min_length=1, max_length=160)
    user_id: str | None = Field(default=None, min_length=1, max_length=36)
    username: str | None = Field(default=None, max_length=150)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    artist_profile_id: str | None = Field(default=None, max_length=36)

    @property
    def resolved_user_id(self) -> str:
        return self.guest_user_id or self.user_id or ""

    @property
    def resolved_display_name(self) -> str:
        return (
            self.guest_display_name
            or self.display_name
            or self.username
            or self.resolved_user_id
        )

    @field_validator("guest_display_name", "display_name")
    @classmethod
    def validate_display_name(_cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("display name must not be blank")
        return stripped


class GuestQuotaRequest(BaseModel):
    quota: int = Field(ge=0, le=500)


class GuestlistEntryResponse(BaseModel):
    id: str
    event_id: str
    event_slug: str
    guest_user_id: str
    guest_display_name: str
    user_id: str
    username: str | None = None
    display_name: str
    source: str
    added_by_user_id: str
    added_by_artist_profile_id: str | None = None
    status: str
    checked_in_at: datetime | None = None
    checked_in_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class GuestQuotaResponse(BaseModel):
    id: str
    event_id: str
    event_slug: str
    artist_profile_id: str
    quota: int
    used: int
    remaining: int


class CheckInTokenResponse(BaseModel):
    token: str
    expires_at: datetime


class CheckInRequest(BaseModel):
    token: str = Field(min_length=20, max_length=240)


class CheckInResponse(BaseModel):
    status: str
    display_name: str
    username: str | None = None


class EventAccessResponse(BaseModel):
    event_id: str
    event_slug: str
    user_id: str
    status: GuestlistEntryStatus
    can_check_in: bool
    checked_in_at: datetime | None = None


class ManagerGuestlistEntryResponse(BaseModel):
    id: str
    guest_user_id: str
    username: str | None = None
    display_name: str
    source: Literal["organizer", "dj"]
    status: GuestlistEntryStatus
    checked_in_at: datetime | None = None


class DoorStaffResponse(BaseModel):
    id: str
    username: str | None = None
    display_name: str | None = None
    assigned_at: datetime


class ViewerLineupArtistResponse(BaseModel):
    artist_profile_id: str
    quota: GuestQuotaResponse | None = None


class EventViewerContextResponse(BaseModel):
    event_id: str
    event_slug: str
    active_guest_access: EventAccessResponse | None = None
    can_mint_qr: bool
    can_manage_guestlist: bool
    can_set_dj_quota: bool
    can_check_in: bool
    can_post_update: bool
    viewer_lineup_artists: list[ViewerLineupArtistResponse]
    quota_summaries: list[GuestQuotaResponse]


class MentionTargetResponse(BaseModel):
    target_type: str
    target_id: str
    handle: str
    display_name: str
    target_url: str


class EventListResponse(BaseModel):
    items: list[EventResponse]
    next_before: str | None = None
