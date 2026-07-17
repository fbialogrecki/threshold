import re
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HTML_TAG_RE = re.compile(r"<[^>]+>")
EVENT_SLUG_RE = re.compile(r"^[a-z0-9-]+$")

# Codepoints allowed inside an emoji sequence besides the base pictographs.
_ZWJ = 0x200D
_VARIATION_SELECTOR = 0xFE0F
_KEYCAP_COMBINER = 0x20E3
_SKIN_TONES = range(0x1F3FB, 0x1F400)
_REGIONAL_INDICATORS = range(0x1F1E6, 0x1F200)
_KEYCAP_BASES = set("0123456789#*")

# Base pictograph blocks (deliberately conservative: no plain letters/digits/punctuation).
_EMOJI_BASE_RANGES = (
    (0x1F300, 0x1F5FF),  # misc symbols and pictographs
    (0x1F600, 0x1F64F),  # emoticons
    (0x1F680, 0x1F6FF),  # transport
    (0x1F900, 0x1F9FF),  # supplemental symbols
    (0x1FA70, 0x1FAFF),  # extended-A
    (0x2600, 0x26FF),  # misc symbols
    (0x2700, 0x27BF),  # dingbats
    (0x2B00, 0x2BFF),  # arrows/stars (⭐ ⬆)
    (0x2190, 0x21FF),  # arrows (↔ with VS16)
    (0x2300, 0x23FF),  # technical (⌚ ⏰)
    (0x25A0, 0x25FF),  # geometric shapes
    (0x2900, 0x297F),  # supplemental arrows
    (0x3030, 0x303D),  # 〰 〽
    (0x3297, 0x3299),  # ㊗ ㊙
    (0x1F004, 0x1F004),  # mahjong tile
    (0x1F0CF, 0x1F0CF),  # joker
    (0x1F170, 0x1F251),  # enclosed alphanumerics/ideographs used as emoji
    (0x00A9, 0x00A9),  # © (with VS16)
    (0x00AE, 0x00AE),  # ® (with VS16)
    (0x2122, 0x2122),  # ™ (with VS16)
)


def _is_emoji_base(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in _EMOJI_BASE_RANGES)


def _segment_is_single_emoji(segment: str) -> bool:
    """Validate one ZWJ-free segment as a single emoji unit."""
    codepoints = [ord(char) for char in segment]
    if not codepoints:
        return False
    # Flag: exactly two regional indicators.
    if all(cp in _REGIONAL_INDICATORS for cp in codepoints):
        return len(codepoints) == 2
    # Keycap: base + optional VS16 + combining keycap.
    if codepoints[-1] == _KEYCAP_COMBINER:
        rest = [cp for cp in codepoints[:-1] if cp != _VARIATION_SELECTOR]
        return len(rest) == 1 and chr(rest[0]) in _KEYCAP_BASES
    # General case: exactly one base pictograph plus optional modifiers.
    bases = 0
    for cp in codepoints:
        if cp == _VARIATION_SELECTOR or cp in _SKIN_TONES:
            continue
        if _is_emoji_base(cp):
            bases += 1
        else:
            return False
    return bases == 1


def is_single_emoji(value: str) -> bool:
    """True when value is one emoji grapheme (incl. ZWJ sequences, flags, keycaps)."""
    if not value or len(value) > 32:
        return False
    segments = value.split(chr(_ZWJ))
    return all(_segment_is_single_emoji(segment) for segment in segments)


def normalize_event_slug(value: str) -> str:
    slug = value.strip().lower()
    if not 3 <= len(slug) <= 160:
        raise ValueError("event slug must be between 3 and 160 characters")
    if not EVENT_SLUG_RE.fullmatch(slug):
        raise ValueError("event slug must contain only lowercase letters, digits, and hyphens")
    return slug


class PostMentionRequest(BaseModel):
    mention_type: str = Field(max_length=32)
    target_handle: str = Field(min_length=1, max_length=150)

    @field_validator("mention_type")
    @classmethod
    def supported_type(_cls, value: str) -> str:
        if value not in {"user", "artist", "page"}:
            raise ValueError("unsupported mention type")
        return value

    @field_validator("target_handle")
    @classmethod
    def normalize_handle(_cls, value: str) -> str:
        handle = value.strip().lstrip("@").lower()
        if not handle:
            raise ValueError("target handle is required")
        return handle


class PostMentionResponse(BaseModel):
    mention_type: str
    target_handle: str
    target_id: str | None = None
    display_name: str | None = None
    target_url: str | None = None
    start_index: int | None = None
    end_index: int | None = None

    model_config = ConfigDict(from_attributes=True)


class GroupResponse(BaseModel):
    id: str
    slug: str
    name: str
    city: str
    scene_tag: str | None = None
    official: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MembershipResponse(BaseModel):
    status: str


class PostCreateRequest(BaseModel):
    group_slug: str | None = Field(default=None, max_length=120)
    event_id: str | None = Field(default=None, min_length=1, max_length=36)
    event_slug: str | None = Field(default=None, min_length=3, max_length=160)
    body: str = Field(min_length=1, max_length=2000)
    mentions: list[PostMentionRequest] = Field(default_factory=list, max_length=20)
    media_asset_ids: list[str] = Field(default_factory=list, max_length=4)

    @field_validator("body")
    @classmethod
    def strip_body(_cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body is required")
        if HTML_TAG_RE.search(stripped):
            raise ValueError("raw HTML is not allowed")
        return stripped

    @field_validator("event_slug", mode="before")
    @classmethod
    def validate_event_slug(_cls, value: object) -> object:
        return normalize_event_slug(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_attachment(self) -> Self:
        if (self.event_id is None) != (self.event_slug is None):
            raise ValueError("event_id and event_slug must be provided together")
        if self.event_id is not None and self.media_asset_ids:
            raise ValueError("posts may attach an image or an event, not both")
        return self


class EventPostCreateRequest(PostCreateRequest):
    event_id: str = Field(min_length=1, max_length=36)
    event_slug: str = Field(min_length=3, max_length=160)
    media_asset_ids: list[str] = Field(default_factory=list, max_length=0)


class EmojiReactionResponse(BaseModel):
    emoji: str
    count: int
    viewer_reacted: bool = False


class PostResponse(BaseModel):
    id: str
    author_user_id: str
    author_username: str
    author_display_name: str
    author_type: str
    group_id: str | None = None
    event_id: str | None = None
    event_slug: str | None = None
    body: str
    created_at: datetime
    edited_at: datetime | None = None
    up_count: int = 0
    down_count: int = 0
    viewer_vote: str | None = None
    viewer_is_author: bool = False
    emoji_reactions: list[EmojiReactionResponse] = Field(default_factory=list)
    # Legacy field kept during rollout (old web reads like_count); mirrors up_count.
    like_count: int = 0
    comment_count: int = 0
    mentions: list[PostMentionResponse] = Field(default_factory=list)
    media_asset_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=1000)
    parent_id: str | None = Field(default=None, max_length=36)
    mentions: list[PostMentionRequest] = Field(default_factory=list, max_length=20)

    @field_validator("body")
    @classmethod
    def strip_body(_cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body is required")
        if HTML_TAG_RE.search(stripped):
            raise ValueError("raw HTML is not allowed")
        return stripped


class CommentResponse(BaseModel):
    id: str
    post_id: str
    parent_id: str | None = None
    author_user_id: str
    author_username: str
    author_display_name: str
    author_type: str
    body: str
    created_at: datetime
    edited_at: datetime | None = None
    up_count: int = 0
    down_count: int = 0
    viewer_vote: str | None = None
    viewer_is_author: bool = False
    mentions: list[PostMentionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PostUpdateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def strip_body(_cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body is required")
        if HTML_TAG_RE.search(stripped):
            raise ValueError("raw HTML is not allowed")
        return stripped


class CommentUpdateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("body")
    @classmethod
    def strip_body(_cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("body is required")
        if HTML_TAG_RE.search(stripped):
            raise ValueError("raw HTML is not allowed")
        return stripped


class ReactionRequest(BaseModel):
    kind: str = "up"

    @field_validator("kind")
    @classmethod
    def supported_kind(_cls, value: str) -> str:
        # "like" stays accepted as an alias for "up" so an older web deploy
        # never receives a 422 mid-rollout (web/social ship independently).
        if value == "like":
            return "up"
        if value not in {"up", "down"}:
            raise ValueError("kind must be 'up' or 'down'")
        return value


class EmojiReactionRequest(BaseModel):
    emoji: str = Field(min_length=1, max_length=32)

    @field_validator("emoji")
    @classmethod
    def single_emoji(_cls, value: str) -> str:
        stripped = value.strip()
        if not is_single_emoji(stripped):
            raise ValueError("must be a single emoji")
        return stripped


class EventAnnouncementRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=36)
    event_slug: str = Field(min_length=3, max_length=160)
    event_title: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=120)
    page_id: str = Field(min_length=1, max_length=36)
    actor_user_id: str = Field(min_length=1, max_length=36)

    @field_validator("event_slug", mode="before")
    @classmethod
    def validate_event_slug(_cls, value: object) -> object:
        return normalize_event_slug(value) if isinstance(value, str) else value


class EventAnnouncementResponse(BaseModel):
    event_id: str
    event_slug: str
    post_id: str
    group_id: str
    created_at: datetime


class EventAnnouncementPostsRequest(BaseModel):
    event_ids: list[str] = Field(default_factory=list, max_length=100)
    event_slugs: list[str] = Field(default_factory=list, max_length=100)

    model_config = ConfigDict(extra="forbid")

    @field_validator("event_ids")
    @classmethod
    def validate_event_ids(_cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 36 for value in values):
            raise ValueError("event IDs must be between 1 and 36 characters")
        return values

    @field_validator("event_slugs")
    @classmethod
    def validate_event_slugs(_cls, values: list[str]) -> list[str]:
        return [normalize_event_slug(value) for value in values]

    @model_validator(mode="after")
    def validate_total_references(self) -> Self:
        if len(self.event_ids) + len(self.event_slugs) > 100:
            raise ValueError("at most 100 event references are allowed")
        return self


class EventAnnouncementPostsResponse(BaseModel):
    posts: list[PostResponse]
    represented_event_ids: list[str]
    represented_event_slugs: list[str]


class SimpleStatusResponse(BaseModel):
    status: str


class SocialCapabilitiesResponse(BaseModel):
    event_post_contract: int = 1


class FeedResponse(BaseModel):
    items: list[PostResponse]
    next_before: str | None = None


class BlockCreateRequest(BaseModel):
    blocked_username: str | None = Field(default=None, max_length=150)

    @field_validator("blocked_username")
    @classmethod
    def normalize_username(_cls, value: str | None) -> str | None:
        if value is None:
            return None
        username = value.strip().lstrip("@").lower()
        return username or None


class BlockResponse(BaseModel):
    blocked_user_id: str
    blocked_username: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportCreateRequest(BaseModel):
    target_type: str = Field(max_length=32)
    target_id: str = Field(min_length=1, max_length=150)
    reason: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("target_type")
    @classmethod
    def supported_target_type(_cls, value: str) -> str:
        if value not in {"post", "comment", "profile", "page"}:
            raise ValueError("unsupported report target")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(_cls, value: str) -> str:
        reason = value.strip().lower().replace(" ", "_")
        if not reason:
            raise ValueError("reason is required")
        return reason

    @field_validator("note")
    @classmethod
    def strip_note(_cls, value: str | None) -> str | None:
        if value is None:
            return None
        note = value.strip()
        return note or None


class ReportDecisionRequest(BaseModel):
    status: str = Field(max_length=32)
    action: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def supported_status(_cls, value: str) -> str:
        if value not in {"open", "reviewing", "resolved", "dismissed"}:
            raise ValueError("unsupported report status")
        return value

    @field_validator("action")
    @classmethod
    def supported_action(_cls, value: str | None) -> str | None:
        if value is not None and value not in {"hide", "delete"}:
            raise ValueError("unsupported moderation action")
        return value


class ReportResponse(BaseModel):
    id: str
    target_type: str
    target_id: str
    reason: str
    note: str | None = None
    status: str
    decision_note: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ModerationReportResponse(ReportResponse):
    reporter_user_id: str


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


class AnonymizeAuthorRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
