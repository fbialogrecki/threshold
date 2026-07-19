import hmac
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from users.account_erasure import enqueue_account_erasure
from users.api.schemas import (
    ActiveUserRefResponse,
    ActiveUserRefsRequest,
    ArtistProfileUpdate,
    ArtistReferenceResponse,
    ArtistReferencesRequest,
    BlockCheckResponse,
    BlockCreateRequest,
    CurrentPrincipalRequest,
    CurrentProfileResponse,
    EmailVerifyRequest,
    EmailVerifyRequestResponse,
    FollowedTargetResponse,
    FollowRequest,
    LoginRequest,
    MentionTargetResponse,
    NotificationCreateRequest,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationResponse,
    OnboardingPreferencesUpdate,
    OrganizerRefResponse,
    OrganizerRefsRequest,
    PageCreateRequest,
    PageManagementResponse,
    PageMembershipResponse,
    PageMembershipUpdateRequest,
    PageUpdateRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    PublicArtistRefResponse,
    PublicArtistResidencyResponse,
    PublicPageRefResponse,
    PublicPageResponse,
    PublicUserProfileResponse,
    RegisterRequest,
    RegisterResponse,
    ReportCreateRequest,
    ReportResponse,
    ResidencyResponse,
    SafetyAuditLogResponse,
    SearchResultItem,
    SimpleStatusResponse,
    TokenResponse,
    UnreadCountResponse,
    UserProfileUpdate,
)
from users.auth.hashing import PasswordPolicyError
from users.auth.service import (
    AuthError,
    DuplicateIdentityError,
    authenticate_user,
    confirm_email_verification,
    confirm_password_reset,
    get_user_by_session_token,
    refresh_session,
    register_user,
    request_email_verification,
    request_password_reset,
    revoke_session,
)
from users.domain.follows import (
    PAGE_FOLLOW_TARGET_TYPES,
    canonical_follow_target_type,
)
from users.domain.models import (
    ApplicationUser,
    ArtistProfile,
    AuthAuditLog,
    ConsumerProfile,
    ContentReport,
    Follow,
    NotificationEvent,
    NotificationPreference,
    OnboardingPreferences,
    Page,
    PageMembership,
    PageMembershipRole,
    PageResidency,
    ResidencyStatus,
    SafetyAuditLog,
    UserBlock,
    utc_now,
)
from users.domain.profiles import (
    get_or_create_current_profile,
    normalize_username,
    update_onboarding_preferences,
)
from users.events import publish_user_block_changed
from users.main_dependencies import get_db_session, settings
from users.media_client import MediaAssetValidationError, validate_avatar_asset

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db_session)]

SESSION_COOKIE = "threshold_session"
REFRESH_COOKIE = "threshold_refresh"
_auth_attempts: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _check_auth_rate_limit(request: Request, endpoint: str, subject: str) -> None:
    now = time.monotonic()
    window_start = now - settings.auth_rate_limit_window_seconds
    keys = (
        f"{endpoint}:ip:{_client_ip(request)}",
        f"{endpoint}:subject:{subject.strip().lower() or 'blank'}",
    )
    for key in keys:
        attempts = _auth_attempts[key]
        while attempts and attempts[0] <= window_start:
            attempts.popleft()
        if len(attempts) >= settings.auth_rate_limit_count:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
            )
    for key in keys:
        _auth_attempts[key].append(now)


def reset_auth_rate_limits_for_tests() -> None:
    _auth_attempts.clear()


class SessionAuthenticationError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=401, detail=detail)


def _lock_active_user_write_domain(session: Session, user_id: str) -> ApplicationUser:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:user_id, 1431520594))"),
            {"user_id": user_id},
        )
    current = session.scalar(
        select(ApplicationUser)
        .where(ApplicationUser.id == user_id)
        .execution_options(populate_existing=True)
    )
    if current is None or current.status != "active":
        raise SessionAuthenticationError("not authenticated")
    return current


def get_current_user(request: Request, session: DbSession) -> ApplicationUser:
    user = get_user_by_session_token(session, settings, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise SessionAuthenticationError("not authenticated")
    return _lock_active_user_write_domain(session, user.id)


ActiveUser = Annotated[ApplicationUser, Depends(get_current_user)]


def require_internal_token(
    token: Annotated[str | None, Header(alias="X-Threshold-Internal-Token")] = None,
) -> None:
    expected = settings.threshold_internal_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="internal token is not configured",
        )
    if token is None or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def _user_payload(user: ApplicationUser) -> dict[str, object]:
    return {
        "id": user.id,
        "authentik_subject": user.authentik_subject,
        "email": user.email,
        "email_normalized": user.email_normalized,
        "email_verified": user.email_verified_at is not None,
        "username": user.username,
        "username_normalized": user.username_normalized,
        "status": user.status,
        "identity_source": user.identity_source,
    }


def _profile_payload(user: ApplicationUser) -> dict[str, object]:
    return {
        "user": _user_payload(user),
        "consumer_profile": user.consumer_profile,
        "onboarding_preferences": user.onboarding_preferences,
        "artist_profile": user.artist_profile,
    }


def _profile_response(user: ApplicationUser) -> CurrentProfileResponse:
    return CurrentProfileResponse.model_validate(_profile_payload(user))


def _set_auth_cookies(response: Response, *, session_token: str, refresh_token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_refresh_ttl_days * 24 * 60 * 60,
        path="/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/v1/auth")


def _validate_avatar_or_422(
    *, asset_id: str, owner_user_id: str, allowed_contexts: set[str]
) -> None:
    try:
        validate_avatar_asset(
            settings,
            asset_id=asset_id,
            owner_user_id=owner_user_id,
            allowed_contexts=allowed_contexts,
        )
    except MediaAssetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _public_avatar_asset_id(
    *, asset_id: str | None, owner_user_id: str | None, allowed_contexts: set[str]
) -> str | None:
    if not asset_id or not owner_user_id:
        return None
    try:
        validate_avatar_asset(
            settings,
            asset_id=asset_id,
            owner_user_id=owner_user_id,
            allowed_contexts=allowed_contexts,
        )
    except MediaAssetValidationError:
        return None
    return asset_id


def _require_page_editor(page: Page, user_id: str) -> None:
    for membership in page.memberships:
        if membership.user_id == user_id and membership.role.value in {"owner", "admin", "editor"}:
            return
    raise HTTPException(status_code=403, detail="not authorized to manage this page")


def _require_page_owner(page: Page, user_id: str) -> None:
    for membership in page.memberships:
        if membership.user_id == user_id and membership.role == PageMembershipRole.owner:
            return
    raise HTTPException(status_code=403, detail="page owner role required")


def _require_page_owner_or_admin(page: Page, user_id: str) -> None:
    for membership in page.memberships:
        if membership.user_id == user_id and membership.role in {
            PageMembershipRole.owner,
            PageMembershipRole.admin,
        }:
            return
    raise HTTPException(status_code=403, detail="page owner/admin role required")


def _artist_ref(user: ApplicationUser) -> PublicArtistRefResponse:
    display_name = (
        user.consumer_profile.display_name
        if user.consumer_profile and user.consumer_profile.display_name
        else (user.username or "")
    )
    return PublicArtistRefResponse(
        username=user.username or "",
        display_name=display_name,
        role=user.artist_profile.role if user.artist_profile else None,
        target_url=f"/u/{user.username or ''}",
    )


def _page_ref(page: Page) -> PublicPageRefResponse:
    return PublicPageRefResponse(
        slug=page.slug,
        display_name=page.display_name,
        page_type=page.page_type,
        target_url=f"/pages/{page.slug}",
    )


def _residency_response(residency: PageResidency) -> ResidencyResponse:
    return ResidencyResponse(
        id=residency.id,
        status=residency.status,
        page=_page_ref(residency.page),
        artist=_artist_ref(residency.artist_user),
        created_at=residency.created_at,
        updated_at=residency.updated_at,
        responded_at=residency.responded_at,
    )


SENSITIVE_AUDIT_KEYS = ("email", "token", "password", "secret", "exact_address")


def _safe_audit_metadata(
    metadata: dict[str, str | int | bool | None],
) -> dict[str, str | int | bool | None]:
    return {
        key: value
        for key, value in metadata.items()
        if not any(marker in key.lower() for marker in SENSITIVE_AUDIT_KEYS)
    }


def _safe_notification_metadata(
    metadata: dict[str, str | int | bool | None],
) -> dict[str, str | int | bool | None]:
    return {
        key: value
        for key, value in metadata.items()
        if not any(marker in key.lower() for marker in SENSITIVE_AUDIT_KEYS)
        and not any(marker in str(value).lower() for marker in SENSITIVE_AUDIT_KEYS)
    }


def _notification_response(row: NotificationEvent) -> NotificationResponse:
    return NotificationResponse(
        id=row.id,
        recipient_user_id=row.user_id,
        actor_user_id=row.actor_user_id,
        type=row.event_type,
        target_type=row.target_type,
        target_id=row.target_id,
        target_url=row.target_url,
        title=row.title,
        body=row.body,
        metadata=row.payload,
        read_at=row.read_at,
        created_at=row.created_at,
    )


CRITICAL_NOTIFICATION_TYPES = {
    "page.member_upserted",
    "page.member_removed",
    "page.owner_assigned",
    "residency.invited",
    "residency.accepted",
    "residency.rejected",
    "guestlist.added",
    "guestlist.removed",
    "guestlist.dj_quota_changed",
    "secret_location.access_granted",
    "secret_location.access_revoked",
}

MENTION_NOTIFICATION_TYPES = {"mention.created", "user.mentioned", "page.mentioned"}
ENGAGEMENT_NOTIFICATION_TYPES = {
    "comment.created",
    "reaction.created",
    "vote.created",
    "follow.created",
}
EVENT_UPDATE_NOTIFICATION_TYPES = {"event.created", "event.updated", "event.post.created"}
PAGE_UPDATE_NOTIFICATION_TYPES = {"page.post.created", "page.updated", "group.post.created"}


def _notification_preferences_response(
    preferences: NotificationPreference,
) -> NotificationPreferenceResponse:
    return NotificationPreferenceResponse(
        mentions_enabled=preferences.mentions_enabled,
        engagement_enabled=preferences.engagement_enabled,
        event_updates_enabled=preferences.event_updates_enabled,
        page_updates_enabled=preferences.page_updates_enabled,
    )


def _get_or_create_notification_preferences(
    session: Session, user_id: str
) -> NotificationPreference:
    preferences = session.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if preferences is not None:
        return preferences
    preferences = NotificationPreference(user_id=user_id)
    session.add(preferences)
    session.flush()
    return preferences


def _notification_category(event_type: str) -> str | None:
    if event_type in MENTION_NOTIFICATION_TYPES or event_type.startswith("mention."):
        return "mentions"
    if event_type in ENGAGEMENT_NOTIFICATION_TYPES:
        return "engagement"
    if event_type in EVENT_UPDATE_NOTIFICATION_TYPES or event_type.startswith("event."):
        return "event_updates"
    if event_type in PAGE_UPDATE_NOTIFICATION_TYPES or event_type.startswith(("page.", "group.")):
        return "page_updates"
    return None


def _notification_allowed_by_preferences(
    session: Session, *, recipient_user_id: str, event_type: str
) -> bool:
    if event_type in CRITICAL_NOTIFICATION_TYPES:
        return True
    category = _notification_category(event_type)
    if category is None:
        return True
    preferences = _get_or_create_notification_preferences(session, recipient_user_id)
    if category == "mentions":
        return preferences.mentions_enabled
    if category == "engagement":
        return preferences.engagement_enabled
    if category == "event_updates":
        return preferences.event_updates_enabled
    if category == "page_updates":
        return preferences.page_updates_enabled
    return True


def _default_notification_dedupe_key(
    *,
    recipient_user_id: str,
    event_type: str,
    target_type: str,
    target_id: str,
    actor_user_id: str | None,
) -> str:
    actor = actor_user_id or "system"
    return f"{event_type}:{target_type}:{target_id}:{actor}:{recipient_user_id}"


def _create_notification(
    session: Session,
    *,
    recipient_user_id: str,
    event_type: str,
    target_type: str,
    target_id: str,
    title: str,
    actor_user_id: str | None = None,
    target_url: str | None = None,
    body: str | None = None,
    dedupe_key: str | None = None,
    metadata: dict[str, str | int | bool | None] | None = None,
) -> NotificationEvent | None:
    if actor_user_id is not None and actor_user_id == recipient_user_id:
        return None
    if actor_user_id is not None and _has_blocked(
        session, blocker_user_id=recipient_user_id, blocked_user_id=actor_user_id
    ):
        return None
    if not _notification_allowed_by_preferences(
        session, recipient_user_id=recipient_user_id, event_type=event_type
    ):
        return None
    dedupe_key = dedupe_key or _default_notification_dedupe_key(
        recipient_user_id=recipient_user_id,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=actor_user_id,
    )
    existing = session.scalar(
        select(NotificationEvent).where(
            NotificationEvent.user_id == recipient_user_id,
            NotificationEvent.dedupe_key == dedupe_key,
        )
    )
    if existing is not None:
        return existing
    row = NotificationEvent(
        user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        target_url=target_url,
        title=title,
        body=body,
        dedupe_key=dedupe_key,
        payload=_safe_notification_metadata(metadata or {}),
    )
    session.add(row)
    return row


def _write_safety_audit(
    session: Session,
    *,
    actor_user_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    reason: str | None = None,
    metadata: dict[str, str | int | bool | None] | None = None,
) -> None:
    session.add(
        SafetyAuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            metadata_json=_safe_audit_metadata(metadata or {}),
        )
    )


def _audit_page_event(
    session: Session,
    *,
    user_id: str,
    event_type: str,
    page_id: str,
    target_user_id: str | None = None,
    role: str | None = None,
) -> None:
    metadata: dict[str, str | int | bool | None] = {
        "page_id": page_id,
        "target_user_id": target_user_id,
        "role": role,
    }
    session.add(
        AuthAuditLog(
            user_id=user_id,
            event_type=event_type,
            result="success",
            metadata_json=metadata,
        )
    )
    _write_safety_audit(
        session,
        actor_user_id=user_id,
        action=event_type,
        target_type="page",
        target_id=page_id,
        reason="page_role",
        metadata=metadata,
    )


def _page_management_response(session: Session, page: Page, role: str) -> PageManagementResponse:
    public = _public_page_response(session, page)
    return PageManagementResponse(id=page.id, role=role, **public.model_dump(exclude={"id"}))


def _notify_user(
    session: Session,
    *,
    user_id: str,
    event_type: str,
    page: Page,
    role: str | None = None,
    actor_user_id: str | None = None,
) -> None:
    _create_notification(
        session,
        recipient_user_id=user_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type="page",
        target_id=page.id,
        target_url=f"/pages/{page.slug}",
        title=f"Page role updated: {role}" if role else "Page role updated",
        dedupe_key=f"{event_type}:{page.id}:{user_id}",
        metadata={
            "page_id": page.id,
            "page_slug": page.slug,
            "page_name": page.display_name,
            "page_type": page.page_type,
            "role": role,
        },
    )


def _has_blocked(session: Session, *, blocker_user_id: str, blocked_user_id: str) -> bool:
    return (
        session.scalar(
            select(UserBlock.id).where(
                UserBlock.blocker_user_id == blocker_user_id,
                UserBlock.blocked_user_id == blocked_user_id,
            )
        )
        is not None
    )


def _publish_block_projection(
    action: str, *, blocker: ApplicationUser, blocked: ApplicationUser
) -> None:
    publish_user_block_changed(
        settings,
        {
            "action": action,
            "blocker_user_id": blocker.id,
            "blocker_username": blocker.username_normalized or blocker.username,
            "blocked_user_id": blocked.id,
            "blocked_username": blocked.username_normalized or blocked.username,
        },
    )


def _resolve_report_target(
    session: Session, *, target_type: str, target_handle: str
) -> tuple[str, str]:
    if target_type == "profile":
        user = session.scalar(
            select(ApplicationUser).where(
                ApplicationUser.username_normalized == normalize_username(target_handle),
                ApplicationUser.status == "active",
            )
        )
        if user is None:
            raise HTTPException(status_code=404, detail="profile not found")
        return user.id, user.username or target_handle
    if target_type == "page":
        page = session.scalar(select(Page).where(Page.slug == target_handle))
        if page is None:
            raise HTTPException(status_code=404, detail="page not found")
        return page.id, page.slug
    return target_handle, target_handle


@router.post("/internal/v1/current-profile", response_model=CurrentProfileResponse)
def current_profile(
    payload: CurrentPrincipalRequest,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> CurrentProfileResponse:
    user = get_or_create_current_profile(
        session,
        authentik_subject=payload.authentik_subject,
        email=payload.email,
        username=payload.username,
    )
    return _profile_response(user)


@router.put(
    "/internal/v1/users/{user_id}/onboarding-preferences",
    response_model=CurrentProfileResponse,
)
def put_onboarding_preferences(
    user_id: str,
    payload: OnboardingPreferencesUpdate,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> CurrentProfileResponse:
    user = session.get(ApplicationUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    update_onboarding_preferences(
        session,
        user_id=user_id,
        city=payload.city,
        preferred_scenes=payload.preferred_scenes,
        onboarding_skipped=False,
    )
    session.refresh(user)
    return _profile_response(user)


@router.post(
    "/internal/v1/pages/organizer-refs",
    response_model=list[OrganizerRefResponse],
)
def get_organizer_refs(
    payload: OrganizerRefsRequest,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> list[OrganizerRefResponse]:
    page_ids = list(dict.fromkeys(payload.page_ids))
    if not page_ids:
        return []
    pages = {
        page_id: OrganizerRefResponse(
            id=page_id,
            slug=slug,
            display_name=display_name,
            page_type=page_type,
            avatar_media_asset_id=avatar_media_asset_id,
            target_url=f"/pages/{slug}",
        )
        for page_id, slug, display_name, page_type, avatar_media_asset_id in session.execute(
            select(
                Page.id,
                Page.slug,
                Page.display_name,
                Page.page_type,
                Page.avatar_media_asset_id,
            ).where(Page.id.in_(page_ids))
        ).tuples()
    }
    return [
        page
        for page_id in page_ids
        if (page := pages.get(page_id)) is not None
    ]


@router.post(
    "/internal/v1/users/active-refs",
    response_model=list[ActiveUserRefResponse],
)
def get_active_user_refs(
    payload: ActiveUserRefsRequest,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> list[ActiveUserRefResponse]:
    user_ids = list(dict.fromkeys(payload.user_ids))
    if not user_ids:
        return []
    refs = {
        user_id: ActiveUserRefResponse(
            id=user_id,
            username=username,
            display_name=display_name or username,
        )
        for user_id, username, display_name in session.execute(
            select(ApplicationUser.id, ApplicationUser.username, ConsumerProfile.display_name)
            .outerjoin(ConsumerProfile, ConsumerProfile.user_id == ApplicationUser.id)
            .where(
                ApplicationUser.id.in_(user_ids),
                ApplicationUser.status == "active",
                ApplicationUser.username.is_not(None),
            )
        ).tuples()
        if username is not None
    }
    return [ref for user_id in user_ids if (ref := refs.get(user_id)) is not None]


@router.get(
    "/internal/v1/pages/{page_id}/members/{user_id}",
    response_model=PageMembershipResponse,
)
def get_page_membership(
    page_id: str,
    user_id: str,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> PageMembershipResponse:
    membership = session.scalar(
        select(PageMembership)
        .join(ApplicationUser, ApplicationUser.id == PageMembership.user_id)
        .where(
            PageMembership.page_id == page_id,
            PageMembership.user_id == user_id,
            ApplicationUser.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="not a member")
    return PageMembershipResponse(role=membership.role.value)


@router.get(
    "/internal/v1/users/{blocker_user_id}/blocks/{blocked_user_id}",
    response_model=BlockCheckResponse,
)
def check_user_block(
    blocker_user_id: str,
    blocked_user_id: str,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> BlockCheckResponse:
    return BlockCheckResponse(
        blocked=_has_blocked(
            session, blocker_user_id=blocker_user_id, blocked_user_id=blocked_user_id
        )
    )


@router.get(
    "/internal/v1/mention-targets/profiles/{handle}",
    response_model=MentionTargetResponse,
)
def resolve_profile_mention_target(
    handle: str,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> MentionTargetResponse:
    user = session.scalar(
        select(ApplicationUser).where(
            ApplicationUser.username_normalized == normalize_username(handle),
            ApplicationUser.status == "active",
        )
    )
    if user is None:
        raise HTTPException(status_code=404, detail="mention target not found")
    display_name = (
        user.consumer_profile.display_name
        if user.consumer_profile and user.consumer_profile.display_name
        else (user.username or handle)
    )
    return MentionTargetResponse(
        target_type="artist" if user.artist_profile is not None else "user",
        target_id=user.id,
        handle=user.username or handle,
        display_name=display_name,
        target_url=f"/profiles/{user.username or handle}",
        recipient_user_id=user.id,
    )


@router.get(
    "/internal/v1/mention-targets/pages/{handle}",
    response_model=MentionTargetResponse,
)
def resolve_page_mention_target(
    handle: str,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> MentionTargetResponse:
    page = session.scalar(select(Page).where(Page.slug == handle.lower()))
    if page is None:
        raise HTTPException(status_code=404, detail="mention target not found")
    return MentionTargetResponse(
        target_type="page",
        target_id=page.id,
        handle=page.slug,
        display_name=page.display_name,
        target_url=f"/pages/{page.slug}",
        recipient_user_id=None,
    )


@router.get(
    "/internal/v1/artist-profiles/{artist_profile_id}",
    response_model=ArtistReferenceResponse,
)
def get_internal_artist_reference(
    artist_profile_id: str,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> ArtistReferenceResponse:
    artist_profile = session.get(ArtistProfile, artist_profile_id)
    user = artist_profile.user if artist_profile is not None else None
    if user is None or user.status != "active" or user.artist_profile is None:
        raise HTTPException(status_code=404, detail="artist profile not found")
    ref = _artist_ref(user)
    return ArtistReferenceResponse(
        artist_profile_id=artist_profile_id,
        user_id=user.id,
        owner_user_id=user.id,
        username=ref.username,
        display_name=ref.display_name,
        target_url=ref.target_url,
    )


@router.post(
    "/internal/v1/artist-profiles/batch",
    response_model=list[ArtistReferenceResponse],
)
def get_internal_artist_references(
    payload: ArtistReferencesRequest,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
) -> list[ArtistReferenceResponse]:
    artist_profile_ids = list(dict.fromkeys(payload.artist_profile_ids))
    if not artist_profile_ids:
        return []
    refs = {
        artist_profile_id: ArtistReferenceResponse(
            artist_profile_id=artist_profile_id,
            user_id=user_id,
            owner_user_id=user_id,
            username=username,
            display_name=display_name or username,
            target_url=f"/u/{username}",
        )
        for artist_profile_id, user_id, username, display_name in session.execute(
            select(
                ArtistProfile.id,
                ApplicationUser.id,
                ApplicationUser.username,
                ConsumerProfile.display_name,
            )
            .join(ApplicationUser, ApplicationUser.id == ArtistProfile.user_id)
            .outerjoin(ConsumerProfile, ConsumerProfile.user_id == ApplicationUser.id)
            .where(
                ArtistProfile.id.in_(artist_profile_ids),
                ApplicationUser.status == "active",
                ApplicationUser.username.is_not(None),
            )
        ).tuples()
        if username is not None
    }
    return [
        ref
        for artist_profile_id in artist_profile_ids
        if (ref := refs.get(artist_profile_id)) is not None
    ]


@router.post(
    "/internal/v1/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_internal_notification(
    payload: NotificationCreateRequest,
    _: Annotated[None, Depends(require_internal_token)],
    session: DbSession,
    response: Response,
) -> NotificationResponse:
    recipient = session.get(ApplicationUser, payload.recipient_user_id)
    if recipient is None or recipient.status != "active":
        raise HTTPException(status_code=404, detail="recipient not found")
    if payload.actor_user_id:
        actor = session.get(ApplicationUser, payload.actor_user_id)
        if actor is None or actor.status != "active":
            raise HTTPException(status_code=404, detail="actor not found")
    dedupe_key = payload.dedupe_key or _default_notification_dedupe_key(
        recipient_user_id=payload.recipient_user_id,
        event_type=payload.type,
        target_type=payload.target_type,
        target_id=payload.target_id,
        actor_user_id=payload.actor_user_id,
    )
    existing = session.scalar(
        select(NotificationEvent).where(
            NotificationEvent.user_id == payload.recipient_user_id,
            NotificationEvent.dedupe_key == dedupe_key,
        )
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return _notification_response(existing)
    row = _create_notification(
        session,
        recipient_user_id=payload.recipient_user_id,
        actor_user_id=payload.actor_user_id,
        event_type=payload.type,
        target_type=payload.target_type,
        target_id=payload.target_id,
        target_url=payload.target_url,
        title=payload.title,
        body=payload.body,
        dedupe_key=dedupe_key,
        metadata=payload.metadata,
    )
    if row is None:
        response.status_code = status.HTTP_200_OK
        return NotificationResponse(
            id="",
            recipient_user_id=payload.recipient_user_id,
            actor_user_id=payload.actor_user_id,
            type=payload.type,
            target_type=payload.target_type,
            target_id=payload.target_id,
            target_url=payload.target_url,
            title=payload.title,
            body=payload.body,
            metadata=_safe_notification_metadata(payload.metadata),
            read_at=None,
            created_at=utc_now(),
        )
    session.commit()
    session.refresh(row)
    return _notification_response(row)


@router.post(
    "/v1/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
def register(
    payload: RegisterRequest, request: Request, response: Response, session: DbSession
) -> RegisterResponse:
    _check_auth_rate_limit(request, "register", payload.email)
    try:
        user, session_token, refresh_token, verification_token = register_user(
            session,
            settings,
            email=payload.email,
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateIdentityError as exc:
        raise HTTPException(status_code=409, detail="email or username already registered") from exc
    _set_auth_cookies(response, session_token=session_token, refresh_token=refresh_token)
    return RegisterResponse.model_validate(
        {
            **_profile_payload(user),
            "dev_email_verification_token": verification_token
            if settings.auth_dev_expose_tokens
            else None,
        }
    )


@router.post("/v1/auth/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, session: DbSession
) -> TokenResponse:
    _check_auth_rate_limit(request, "login", payload.email_or_username)
    try:
        user, session_token, refresh_token = authenticate_user(
            session,
            settings,
            email_or_username=payload.email_or_username,
            password=payload.password,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail="invalid credentials") from exc
    _set_auth_cookies(response, session_token=session_token, refresh_token=refresh_token)
    return TokenResponse.model_validate(_profile_payload(user))


@router.get("/v1/auth/me", response_model=CurrentProfileResponse)
def me(request: Request, session: DbSession) -> CurrentProfileResponse:
    user = get_current_user(request, session)
    return _profile_response(user)


@router.post("/v1/auth/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, session: DbSession) -> TokenResponse:
    try:
        user, session_token, refresh_token = refresh_session(
            session, settings, request.cookies.get(REFRESH_COOKIE)
        )
    except AuthError as exc:
        raise SessionAuthenticationError("invalid refresh token") from exc
    _set_auth_cookies(response, session_token=session_token, refresh_token=refresh_token)
    return TokenResponse.model_validate(_profile_payload(user))


@router.post("/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: DbSession) -> Response:
    revoke_session(
        session,
        settings,
        session_token=request.cookies.get(SESSION_COOKIE),
        refresh_token=request.cookies.get(REFRESH_COOKIE),
    )
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/v1/auth/email/verify/request", response_model=EmailVerifyRequestResponse)
def email_verify_request(request: Request, session: DbSession) -> EmailVerifyRequestResponse:
    session_cookie = request.cookies.get(SESSION_COOKIE) or ""
    _check_auth_rate_limit(request, "email_verify_request", session_cookie)
    user = get_current_user(request, session)
    token = request_email_verification(session, settings, user)
    return EmailVerifyRequestResponse(
        status="ok", dev_email_verification_token=token if settings.auth_dev_expose_tokens else None
    )


@router.post("/v1/auth/email/verify/confirm", response_model=CurrentProfileResponse)
def email_verify_confirm(
    payload: EmailVerifyRequest, request: Request, session: DbSession
) -> CurrentProfileResponse:
    _check_auth_rate_limit(request, "email_verify_confirm", payload.token)
    try:
        user = confirm_email_verification(session, settings, payload.token)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail="invalid verification token") from exc
    return _profile_response(user)


@router.post("/v1/auth/password/reset/request", response_model=PasswordResetRequestResponse)
def password_reset_request(
    payload: PasswordResetRequest, request: Request, session: DbSession
) -> PasswordResetRequestResponse:
    _check_auth_rate_limit(request, "password_reset_request", payload.email)
    token = request_password_reset(session, settings, payload.email)
    return PasswordResetRequestResponse(
        status="ok", dev_password_reset_token=token if settings.auth_dev_expose_tokens else None
    )


@router.post("/v1/auth/password/reset/confirm", response_model=SimpleStatusResponse)
def password_reset_confirm(
    payload: PasswordResetConfirmRequest, request: Request, session: DbSession
) -> SimpleStatusResponse:
    _check_auth_rate_limit(request, "password_reset_confirm", payload.token)
    try:
        confirm_password_reset(
            session, settings, token=payload.token, new_password=payload.new_password
        )
    except (AuthError, PasswordPolicyError) as exc:
        raise HTTPException(status_code=400, detail="invalid reset token or password") from exc
    return SimpleStatusResponse(status="ok")


@router.put("/v1/me/onboarding", response_model=CurrentProfileResponse)
def update_me_onboarding(
    payload: OnboardingPreferencesUpdate,
    user: ActiveUser,
    session: DbSession,
) -> CurrentProfileResponse:
    if user.onboarding_preferences is None:
        user.onboarding_preferences = OnboardingPreferences()
    user.onboarding_preferences.city = payload.city
    user.onboarding_preferences.preferred_scenes = payload.preferred_scenes
    user.onboarding_preferences.onboarding_skipped = False
    session.add(user)
    session.commit()
    session.refresh(user)
    return _profile_response(user)


@router.patch("/v1/me/profile", response_model=CurrentProfileResponse)
def update_me_profile(
    payload: UserProfileUpdate,
    user: ActiveUser,
    session: DbSession,
) -> CurrentProfileResponse:
    if payload.username is not None:
        norm_username = normalize_username(payload.username)
        existing_user = session.scalar(
            select(ApplicationUser).where(
                ApplicationUser.username_normalized == norm_username,
                ApplicationUser.id != user.id,
            )
        )
        if existing_user is not None:
            raise HTTPException(status_code=409, detail="username already taken")
        user.username = payload.username
        user.username_normalized = norm_username

    if payload.display_name is not None:
        if user.consumer_profile is None:
            user.consumer_profile = ConsumerProfile(display_name=payload.display_name)
        else:
            user.consumer_profile.display_name = payload.display_name

    if payload.bio is not None:
        if user.consumer_profile is None:
            user.consumer_profile = ConsumerProfile(bio=payload.bio)
        else:
            user.consumer_profile.bio = payload.bio

    if payload.avatar_media_asset_id is not None:
        _validate_avatar_or_422(
            asset_id=payload.avatar_media_asset_id,
            owner_user_id=user.id,
            allowed_contexts={"user_avatar"},
        )
        if user.consumer_profile is None:
            user.consumer_profile = ConsumerProfile(
                avatar_media_asset_id=payload.avatar_media_asset_id
            )
        else:
            user.consumer_profile.avatar_media_asset_id = payload.avatar_media_asset_id

    if payload.city is not None:
        if user.onboarding_preferences is None:
            user.onboarding_preferences = OnboardingPreferences(city=payload.city)
        else:
            user.onboarding_preferences.city = payload.city

    session.add(user)
    session.commit()
    session.refresh(user)
    return _profile_response(user)


@router.post("/v1/me/artist", response_model=CurrentProfileResponse)
def create_or_update_artist_profile(
    payload: ArtistProfileUpdate,
    user: ActiveUser,
    session: DbSession,
) -> CurrentProfileResponse:
    if user.artist_profile is None:
        user.artist_profile = ArtistProfile(
            role=payload.role,
            location=payload.location,
            links=payload.links,
        )
    else:
        user.artist_profile.role = payload.role
        user.artist_profile.location = payload.location
        user.artist_profile.links = payload.links

    session.add(user)
    session.commit()
    session.refresh(user)
    return _profile_response(user)


@router.delete("/v1/me", status_code=status.HTTP_202_ACCEPTED)
def delete_me_account(
    user: ActiveUser,
    response: Response,
    session: DbSession,
) -> Response:
    enqueue_account_erasure(session, user)
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_202_ACCEPTED
    return response


@router.post("/v1/me/follows", response_model=SimpleStatusResponse)
def follow_target(
    payload: FollowRequest,
    user: ActiveUser,
    session: DbSession,
) -> SimpleStatusResponse:
    target_type = canonical_follow_target_type(payload.target_type)
    target_handle = payload.target_handle
    target_id: str | None = None

    if target_type == "consumer":
        norm_handle = normalize_username(target_handle)
        target_user = session.scalar(
            select(ApplicationUser).where(ApplicationUser.username_normalized == norm_handle)
        )
        if target_user is None or target_user.status != "active":
            raise HTTPException(status_code=404, detail="target consumer not found")
        target_id = target_user.id
        target_handle = target_user.username or target_handle
    elif target_type == "artist":
        norm_handle = normalize_username(target_handle)
        target_user = session.scalar(
            select(ApplicationUser).where(ApplicationUser.username_normalized == norm_handle)
        )
        if (
            target_user is None
            or target_user.status != "active"
            or target_user.artist_profile is None
        ):
            raise HTTPException(status_code=404, detail="target artist not found")
        target_id = target_user.id
        target_handle = target_user.username or target_handle
    elif target_type == "page":
        page = session.scalar(select(Page).where(Page.slug == target_handle))
        if page is None:
            raise HTTPException(status_code=404, detail=f"target {target_type} not found")
        target_id = page.id
        target_handle = page.slug

    if not target_id:
        raise HTTPException(status_code=404, detail="target not found")

    existing_target_types = PAGE_FOLLOW_TARGET_TYPES if target_type == "page" else {target_type}
    existing_follow = session.scalar(
        select(Follow).where(
            Follow.follower_user_id == user.id,
            Follow.target_type.in_(existing_target_types),
            Follow.target_id == target_id,
        )
    )
    if existing_follow is not None:
        return SimpleStatusResponse(status="ok")

    new_follow = Follow(
        follower_user_id=user.id,
        target_type=target_type,
        target_id=target_id,
        target_handle=target_handle,
    )
    session.add(new_follow)
    if target_type in {"consumer", "artist"}:
        _create_notification(
            session,
            recipient_user_id=target_id,
            actor_user_id=user.id,
            event_type="follow.created",
            target_type=target_type,
            target_id=target_id,
            target_url=f"/u/{user.username}",
            title=f"{user.username or 'Someone'} followed you",
            dedupe_key=f"follow:{user.id}:{target_id}",
            metadata={
                "target_handle": target_handle,
                "actor_username": user.username,
                "actor_display_name": (
                    user.consumer_profile.display_name
                    if user.consumer_profile and user.consumer_profile.display_name
                    else user.username
                ),
            },
        )
    session.commit()
    return SimpleStatusResponse(status="ok")


@router.delete(
    "/v1/me/follows/{target_type}/{target_handle}", status_code=status.HTTP_204_NO_CONTENT
)
def unfollow_target(
    target_type: str,
    target_handle: str,
    user: ActiveUser,
    session: DbSession,
    response: Response,
) -> Response:
    if target_type not in {"artist", "consumer", *PAGE_FOLLOW_TARGET_TYPES}:
        raise HTTPException(status_code=400, detail="invalid target_type")

    target_type = canonical_follow_target_type(target_type)
    if target_type == "page":
        page = session.scalar(
            select(Page).where(func.lower(Page.slug) == target_handle.lower())
        )
        follows = (
            session.scalars(
                select(Follow).where(
                    Follow.follower_user_id == user.id,
                    Follow.target_type.in_(PAGE_FOLLOW_TARGET_TYPES),
                    Follow.target_id == page.id,
                )
            ).all()
            if page is not None
            else []
        )
    else:
        follows = [
            follow
            for follow in session.scalars(
                select(Follow).where(
                    Follow.follower_user_id == user.id,
                    Follow.target_type == target_type,
                )
            ).all()
            if follow.target_handle.lower() == target_handle.lower()
        ]

    if follows:
        for follow in follows:
            session.delete(follow)
        session.commit()

    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/v1/me/follows", response_model=list[FollowedTargetResponse])
def get_followed_targets(
    user: ActiveUser,
    session: DbSession,
) -> list[FollowedTargetResponse]:
    follows = session.scalars(select(Follow).where(Follow.follower_user_id == user.id)).all()

    results = []
    seen: set[tuple[str, str]] = set()
    for f in follows:
        target_type = canonical_follow_target_type(f.target_type)
        key = (target_type, f.target_id)
        if key in seen:
            continue
        seen.add(key)
        display_name = f.target_handle
        if target_type in {"consumer", "artist"}:
            target_user = session.get(ApplicationUser, f.target_id)
            if target_user is not None and target_user.status == "active":
                if (
                    target_user.consumer_profile is not None
                    and target_user.consumer_profile.display_name
                ):
                    display_name = target_user.consumer_profile.display_name
                elif target_user.username:
                    display_name = target_user.username
        elif target_type == "page":
            page = session.get(Page, f.target_id)
            if page is not None:
                display_name = page.display_name

        results.append(
            FollowedTargetResponse(
                target_type=target_type,
                target_id=f.target_id,
                target_handle=f.target_handle,
                display_name=display_name,
            )
        )
    return results


@router.post(
    "/v1/me/blocks", response_model=SimpleStatusResponse, status_code=status.HTTP_201_CREATED
)
def block_user(
    payload: BlockCreateRequest,
    user: ActiveUser,
    session: DbSession,
) -> SimpleStatusResponse:
    target = session.scalar(
        select(ApplicationUser).where(
            ApplicationUser.username_normalized == normalize_username(payload.username),
            ApplicationUser.status == "active",
        )
    )
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="cannot block yourself")
    if _has_blocked(session, blocker_user_id=user.id, blocked_user_id=target.id):
        _publish_block_projection("blocked", blocker=user, blocked=target)
        return SimpleStatusResponse(status="ok")
    session.add(UserBlock(blocker_user_id=user.id, blocked_user_id=target.id))
    _write_safety_audit(
        session,
        actor_user_id=user.id,
        action="user.blocked",
        target_type="user",
        target_id=target.id,
        reason="block",
        metadata={"target_username": target.username_normalized},
    )
    session.commit()
    _publish_block_projection("blocked", blocker=user, blocked=target)
    return SimpleStatusResponse(status="ok")


@router.delete("/v1/me/blocks/{username}", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(username: str, user: ActiveUser, session: DbSession) -> Response:
    target = session.scalar(
        select(ApplicationUser).where(
            ApplicationUser.username_normalized == normalize_username(username),
            ApplicationUser.status == "active",
        )
    )
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")
    block = session.scalar(
        select(UserBlock).where(
            UserBlock.blocker_user_id == user.id,
            UserBlock.blocked_user_id == target.id,
        )
    )
    if block is not None:
        session.delete(block)
        _write_safety_audit(
            session,
            actor_user_id=user.id,
            action="user.unblocked",
            target_type="user",
            target_id=target.id,
            reason="unblock",
            metadata={"target_username": target.username_normalized},
        )
        session.commit()
    _publish_block_projection("unblocked", blocker=user, blocked=target)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/v1/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreateRequest,
    user: ActiveUser,
    session: DbSession,
) -> ReportResponse:
    target_id, target_handle = _resolve_report_target(
        session, target_type=payload.target_type, target_handle=payload.target_handle
    )
    report = ContentReport(
        reporter_user_id=user.id,
        target_type=payload.target_type,
        target_id=target_id,
        target_handle=target_handle,
        reason=payload.reason,
        note=payload.note,
    )
    session.add(report)
    _write_safety_audit(
        session,
        actor_user_id=user.id,
        action="report.created",
        target_type=payload.target_type,
        target_id=target_id,
        reason=payload.reason,
        metadata={"target_handle": target_handle},
    )
    session.commit()
    session.refresh(report)
    return ReportResponse.model_validate(report)


@router.get("/v1/notifications/preferences", response_model=NotificationPreferenceResponse)
def get_notification_preferences(
    user: ActiveUser, session: DbSession
) -> NotificationPreferenceResponse:
    preferences = _get_or_create_notification_preferences(session, user.id)
    session.commit()
    return _notification_preferences_response(preferences)


@router.put("/v1/notifications/preferences", response_model=NotificationPreferenceResponse)
def update_notification_preferences(
    payload: NotificationPreferenceUpdate, user: ActiveUser, session: DbSession
) -> NotificationPreferenceResponse:
    preferences = _get_or_create_notification_preferences(session, user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(preferences, field, value)
    session.commit()
    session.refresh(preferences)
    return _notification_preferences_response(preferences)


@router.get("/v1/notifications", response_model=list[NotificationResponse])
def list_notifications(user: ActiveUser, session: DbSession) -> list[NotificationResponse]:
    rows = session.scalars(
        select(NotificationEvent)
        .where(NotificationEvent.user_id == user.id)
        .order_by(NotificationEvent.created_at.desc(), NotificationEvent.id.desc())
        .limit(50)
    ).all()
    return [_notification_response(row) for row in rows]


@router.get("/v1/notifications/unread-count", response_model=UnreadCountResponse)
def notifications_unread_count(user: ActiveUser, session: DbSession) -> UnreadCountResponse:
    count = session.scalar(
        select(func.count(NotificationEvent.id)).where(
            NotificationEvent.user_id == user.id, NotificationEvent.read_at.is_(None)
        )
    )
    return UnreadCountResponse(count=count or 0)


@router.post("/v1/notifications/{notification_id}/read", response_model=SimpleStatusResponse)
def mark_notification_read(
    notification_id: str, user: ActiveUser, session: DbSession
) -> SimpleStatusResponse:
    row = session.scalar(
        select(NotificationEvent).where(
            NotificationEvent.id == notification_id, NotificationEvent.user_id == user.id
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="notification not found")
    if row.read_at is None:
        row.read_at = utc_now()
        session.commit()
    return SimpleStatusResponse(status="ok")


@router.post("/v1/notifications/read-all", response_model=SimpleStatusResponse)
def mark_all_notifications_read(user: ActiveUser, session: DbSession) -> SimpleStatusResponse:
    rows = session.scalars(
        select(NotificationEvent).where(
            NotificationEvent.user_id == user.id, NotificationEvent.read_at.is_(None)
        )
    ).all()
    now = utc_now()
    for row in rows:
        row.read_at = now
    session.commit()
    return SimpleStatusResponse(status="ok")


@router.get("/v1/safety/audit-log", response_model=list[SafetyAuditLogResponse])
def list_safety_audit_log(user: ActiveUser, session: DbSession) -> list[SafetyAuditLogResponse]:
    rows = session.scalars(
        select(SafetyAuditLog)
        .where(SafetyAuditLog.actor_user_id == user.id)
        .order_by(SafetyAuditLog.created_at, SafetyAuditLog.id)
    ).all()
    return [
        SafetyAuditLogResponse.model_validate(
            {
                "id": row.id,
                "actor_user_id": row.actor_user_id,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "reason": row.reason,
                "metadata": row.metadata_json,
                "created_at": row.created_at,
            }
        )
        for row in rows
    ]


@router.get("/v1/moderation/reports", response_model=list[ReportResponse])
def list_moderation_reports(user: ActiveUser, session: DbSession) -> list[ReportResponse]:
    page_ids = session.scalars(
        select(PageMembership.page_id).where(
            PageMembership.user_id == user.id,
            PageMembership.role.in_([PageMembershipRole.owner, PageMembershipRole.admin]),
        )
    ).all()
    reports = session.scalars(
        select(ContentReport)
        .where(
            ContentReport.status == "open",
            ((ContentReport.target_type == "profile") & (ContentReport.target_id == user.id))
            | ((ContentReport.target_type == "page") & ContentReport.target_id.in_(page_ids)),
        )
        .order_by(ContentReport.created_at.desc())
    ).all()
    return [ReportResponse.model_validate(report) for report in reports]


@router.get("/v1/profiles/{username}", response_model=PublicUserProfileResponse)
def get_public_profile(username: str, session: DbSession) -> PublicUserProfileResponse:
    norm_username = normalize_username(username)
    user = session.scalar(
        select(ApplicationUser).where(
            ApplicationUser.username_normalized == norm_username,
            ApplicationUser.status == "active",
        )
    )
    if user is None:
        raise HTTPException(status_code=404, detail="profile not found")

    follower_count = (
        session.scalar(
            select(func.count(Follow.id)).where(
                Follow.target_id == user.id, Follow.target_type.in_({"consumer", "artist"})
            )
        )
        or 0
    )

    artist_profile = user.artist_profile
    is_artist = artist_profile is not None
    return PublicUserProfileResponse(
        id=user.id,
        type="artist" if is_artist else "consumer",
        username=user.username or "",
        artist_profile_id=artist_profile.id if artist_profile else None,
        display_name=user.consumer_profile.display_name
        if user.consumer_profile and user.consumer_profile.display_name
        else (user.username or ""),
        bio=user.consumer_profile.bio if user.consumer_profile else None,
        avatar_media_asset_id=_public_avatar_asset_id(
            asset_id=user.consumer_profile.avatar_media_asset_id if user.consumer_profile else None,
            owner_user_id=user.id,
            allowed_contexts={"user_avatar"},
        ),
        role=artist_profile.role if artist_profile else None,
        location=artist_profile.location if artist_profile else None,
        links=artist_profile.links if artist_profile else [],
        follower_count=follower_count,
        residencies=[
            PublicArtistResidencyResponse(
                page_slug=residency.page.slug,
                page_name=residency.page.display_name,
                page_type=residency.page.page_type,
                target_url=f"/pages/{residency.page.slug}",
            )
            for residency in session.scalars(
                select(PageResidency)
                .where(
                    PageResidency.artist_user_id == user.id,
                    PageResidency.status == ResidencyStatus.accepted.value,
                )
                .order_by(PageResidency.updated_at.desc(), PageResidency.id.desc())
            ).all()
        ],
    )


def _public_page_response(
    session: Session,
    page: Page,
    viewer: ApplicationUser | None = None,
) -> PublicPageResponse:
    follower_count = (
        session.scalar(
            select(func.count(func.distinct(Follow.follower_user_id))).where(
                Follow.target_id == page.id,
                Follow.target_type.in_(PAGE_FOLLOW_TARGET_TYPES),
            )
        )
        or 0
    )
    is_following = viewer is not None and session.scalar(
        select(Follow.id).where(
            Follow.follower_user_id == viewer.id,
            Follow.target_id == page.id,
            Follow.target_type.in_(PAGE_FOLLOW_TARGET_TYPES),
        )
    ) is not None

    return PublicPageResponse(
        id=page.id,
        slug=page.slug,
        display_name=page.display_name,
        page_type=page.page_type,
        city=page.city,
        about=page.about,
        links=page.links,
        avatar_media_asset_id=_public_avatar_asset_id(
            asset_id=page.avatar_media_asset_id,
            owner_user_id=page.avatar_media_owner_user_id,
            allowed_contexts={"page_avatar"},
        ),
        residents=[
            _artist_ref(residency.artist_user)
            for residency in session.scalars(
                select(PageResidency)
                .where(
                    PageResidency.page_id == page.id,
                    PageResidency.status == ResidencyStatus.accepted.value,
                )
                .order_by(PageResidency.updated_at.desc(), PageResidency.id.desc())
            ).all()
        ],
        follower_count=follower_count,
        is_following=is_following,
    )


@router.get("/v1/pages/{slug}", response_model=PublicPageResponse)
def get_public_page(slug: str, request: Request, session: DbSession) -> PublicPageResponse:
    page = session.scalar(select(Page).where(Page.slug == slug))
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    viewer = get_user_by_session_token(
        session, settings, request.cookies.get(SESSION_COOKIE)
    )
    return _public_page_response(session, page, viewer)


@router.post(
    "/v1/pages",
    response_model=PageManagementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_page(
    payload: PageCreateRequest,
    user: ActiveUser,
    session: DbSession,
) -> PageManagementResponse:
    existing_page = session.scalar(select(Page).where(Page.slug == payload.slug))
    if existing_page is not None:
        raise HTTPException(status_code=409, detail="page slug already taken")
    page = Page(
        slug=payload.slug,
        display_name=payload.display_name,
        page_type=payload.page_type,
        city=payload.city,
        about=payload.about,
        links=payload.links,
    )
    session.add(page)
    session.flush()
    session.add(PageMembership(page_id=page.id, user_id=user.id, role=PageMembershipRole.owner))
    _audit_page_event(session, user_id=user.id, event_type="page.created", page_id=page.id)
    _notify_user(
        session, user_id=user.id, event_type="page.owner_assigned", page=page, role="owner"
    )
    session.commit()
    session.refresh(page)
    return _page_management_response(session, page, "owner")


@router.get("/v1/me/pages", response_model=list[PageManagementResponse])
def list_managed_pages(user: ActiveUser, session: DbSession) -> list[PageManagementResponse]:
    memberships = session.scalars(
        select(PageMembership).where(PageMembership.user_id == user.id)
    ).all()
    return [
        _page_management_response(session, membership.page, membership.role.value)
        for membership in memberships
    ]


@router.post(
    "/v1/pages/{slug}/residencies/{username}/invite",
    response_model=ResidencyResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/v1/pages/{slug}/residency-invitations/{username}",
    response_model=ResidencyResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_page_residency(
    slug: str,
    username: str,
    user: ActiveUser,
    session: DbSession,
) -> ResidencyResponse:
    page = session.scalar(select(Page).where(Page.slug == slug))
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    _require_page_owner_or_admin(page, user.id)
    artist = session.scalar(
        select(ApplicationUser).where(
            ApplicationUser.username_normalized == normalize_username(username),
            ApplicationUser.status == "active",
        )
    )
    if artist is None or artist.artist_profile is None:
        raise HTTPException(status_code=404, detail="artist not found")
    if artist.id == user.id:
        raise HTTPException(status_code=400, detail="cannot invite yourself")
    residency = session.scalar(
        select(PageResidency).where(
            PageResidency.page_id == page.id,
            PageResidency.artist_user_id == artist.id,
        )
    )
    if residency is None:
        residency = PageResidency(
            page_id=page.id,
            artist_user_id=artist.id,
            invited_by_user_id=user.id,
        )
    else:
        residency.status = ResidencyStatus.pending.value
        residency.invited_by_user_id = user.id
        residency.responded_at = None
    session.add(residency)
    session.flush()
    _write_safety_audit(
        session,
        actor_user_id=user.id,
        action="residency.invited",
        target_type="residency",
        target_id=residency.id,
        reason="page_residency",
        metadata={"page_id": page.id, "artist_user_id": artist.id},
    )
    _create_notification(
        session,
        recipient_user_id=artist.id,
        actor_user_id=user.id,
        event_type="residency.invited",
        target_type="residency",
        target_id=residency.id,
        target_url=f"/pages/{page.slug}",
        title=f"{page.display_name} invited you as resident",
        dedupe_key=f"residency.invited:{residency.id}:{artist.id}",
        metadata={
            "page_id": page.id,
            "page_slug": page.slug,
            "page_name": page.display_name,
        },
    )
    session.commit()
    session.refresh(residency)
    return _residency_response(residency)


@router.post("/v1/me/residencies/{residency_id}/accept", response_model=ResidencyResponse)
def accept_residency(
    residency_id: str,
    user: ActiveUser,
    session: DbSession,
) -> ResidencyResponse:
    residency = session.get(PageResidency, residency_id)
    if residency is None or residency.artist_user_id != user.id:
        raise HTTPException(status_code=404, detail="residency not found")
    residency.status = ResidencyStatus.accepted.value
    residency.responded_at = utc_now()
    session.add(residency)
    _write_safety_audit(
        session,
        actor_user_id=user.id,
        action="residency.accepted",
        target_type="residency",
        target_id=residency.id,
        reason="page_residency",
        metadata={
            "page_id": residency.page_id,
            "page_slug": residency.page.slug,
            "page_name": residency.page.display_name,
            "artist_user_id": user.id,
            "actor_username": user.username,
            "actor_display_name": (
                user.consumer_profile.display_name
                if user.consumer_profile and user.consumer_profile.display_name
                else user.username
            ),
        },
    )
    _create_notification(
        session,
        recipient_user_id=residency.invited_by_user_id,
        actor_user_id=user.id,
        event_type="residency.accepted",
        target_type="residency",
        target_id=residency.id,
        target_url=f"/pages/{residency.page.slug}",
        title=f"{user.username or 'Artist'} accepted residency",
        dedupe_key=f"residency.accepted:{residency.id}:{residency.invited_by_user_id}",
        metadata={
            "page_id": residency.page_id,
            "page_slug": residency.page.slug,
            "page_name": residency.page.display_name,
            "artist_user_id": user.id,
            "actor_username": user.username,
            "actor_display_name": (
                user.consumer_profile.display_name
                if user.consumer_profile and user.consumer_profile.display_name
                else user.username
            ),
        },
    )
    session.commit()
    session.refresh(residency)
    return _residency_response(residency)


@router.post("/v1/me/residencies/{residency_id}/reject", response_model=ResidencyResponse)
def reject_residency(
    residency_id: str,
    user: ActiveUser,
    session: DbSession,
) -> ResidencyResponse:
    residency = session.get(PageResidency, residency_id)
    if residency is None or residency.artist_user_id != user.id:
        raise HTTPException(status_code=404, detail="residency not found")
    residency.status = ResidencyStatus.rejected.value
    residency.responded_at = utc_now()
    session.add(residency)
    _write_safety_audit(
        session,
        actor_user_id=user.id,
        action="residency.rejected",
        target_type="residency",
        target_id=residency.id,
        reason="page_residency",
        metadata={"page_id": residency.page_id, "artist_user_id": user.id},
    )
    _create_notification(
        session,
        recipient_user_id=residency.invited_by_user_id,
        actor_user_id=user.id,
        event_type="residency.rejected",
        target_type="residency",
        target_id=residency.id,
        target_url=f"/pages/{residency.page.slug}",
        title=f"{user.username or 'Artist'} rejected residency",
        dedupe_key=f"residency.rejected:{residency.id}:{residency.invited_by_user_id}",
        metadata={
            "page_id": residency.page_id,
            "page_slug": residency.page.slug,
            "page_name": residency.page.display_name,
            "artist_user_id": user.id,
            "actor_username": user.username,
            "actor_display_name": (
                user.consumer_profile.display_name
                if user.consumer_profile and user.consumer_profile.display_name
                else user.username
            ),
        },
    )
    session.commit()
    session.refresh(residency)
    return _residency_response(residency)


@router.patch("/v1/pages/{slug}", response_model=PublicPageResponse)
def update_page(
    slug: str,
    payload: PageUpdateRequest,
    user: ActiveUser,
    session: DbSession,
) -> PublicPageResponse:
    page = session.scalar(select(Page).where(Page.slug == slug))
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    _require_page_editor(page, user.id)
    if payload.avatar_media_asset_id is not None:
        _validate_avatar_or_422(
            asset_id=payload.avatar_media_asset_id,
            owner_user_id=user.id,
            allowed_contexts={"page_avatar"},
        )
        page.avatar_media_asset_id = payload.avatar_media_asset_id
        page.avatar_media_owner_user_id = user.id
    session.add(page)
    session.commit()
    session.refresh(page)
    return _public_page_response(session, page, user)


@router.get("/v1/pages/{slug}/members", response_model=list[PageMembershipResponse])
def list_page_members(
    slug: str,
    user: ActiveUser,
    session: DbSession,
) -> list[PageMembershipResponse]:
    page = session.scalar(select(Page).where(Page.slug == slug))
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    _require_page_editor(page, user.id)
    return [PageMembershipResponse(role=membership.role.value) for membership in page.memberships]


@router.put("/v1/pages/{slug}/members/{username}", response_model=PageMembershipResponse)
def upsert_page_member(
    slug: str,
    username: str,
    payload: PageMembershipUpdateRequest,
    user: ActiveUser,
    session: DbSession,
) -> PageMembershipResponse:
    page = session.scalar(select(Page).where(Page.slug == slug))
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    _require_page_owner(page, user.id)
    target = session.scalar(
        select(ApplicationUser).where(
            ApplicationUser.username_normalized == normalize_username(username)
        )
    )
    if target is None or target.status != "active":
        raise HTTPException(status_code=404, detail="user not found")
    membership = session.scalar(
        select(PageMembership).where(
            PageMembership.page_id == page.id,
            PageMembership.user_id == target.id,
        )
    )
    if membership is not None and membership.role == PageMembershipRole.owner:
        raise HTTPException(status_code=400, detail="owner role cannot be changed")
    role = PageMembershipRole(payload.role)
    if membership is None:
        membership = PageMembership(page_id=page.id, user_id=target.id, role=role)
    else:
        membership.role = role
    session.add(membership)
    _audit_page_event(
        session,
        user_id=user.id,
        event_type="page.member_upserted",
        page_id=page.id,
        target_user_id=target.id,
        role=role.value,
    )
    _notify_user(
        session,
        user_id=target.id,
        actor_user_id=user.id,
        event_type="page.member_upserted",
        page=page,
        role=role.value,
    )
    session.commit()
    return PageMembershipResponse(role=membership.role.value)


@router.delete("/v1/pages/{slug}/members/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page_member(
    slug: str,
    username: str,
    user: ActiveUser,
    session: DbSession,
    response: Response,
) -> Response:
    page = session.scalar(select(Page).where(Page.slug == slug))
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    _require_page_owner(page, user.id)
    target = session.scalar(
        select(ApplicationUser).where(
            ApplicationUser.username_normalized == normalize_username(username)
        )
    )
    if target is None:
        raise HTTPException(status_code=404, detail="user not found")
    membership = session.scalar(
        select(PageMembership).where(
            PageMembership.page_id == page.id,
            PageMembership.user_id == target.id,
        )
    )
    if membership is None:
        response.status_code = status.HTTP_204_NO_CONTENT
        return response
    if membership.role == PageMembershipRole.owner:
        raise HTTPException(status_code=400, detail="owner role cannot be removed")
    removed_role = membership.role.value
    session.delete(membership)
    _audit_page_event(
        session,
        user_id=user.id,
        event_type="page.member_removed",
        page_id=page.id,
        target_user_id=target.id,
        role=removed_role,
    )
    _notify_user(
        session,
        user_id=target.id,
        actor_user_id=user.id,
        event_type="page.member_removed",
        page=page,
        role=removed_role,
    )
    session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/v1/search", response_model=list[SearchResultItem])
def search_entities(q: str, session: DbSession, type: str | None = None) -> list[SearchResultItem]:
    results: list[SearchResultItem] = []
    q_clean = q.strip().lstrip("@#")
    if not q_clean:
        return results

    if type is None or type == "profiles":
        # Search users
        users = session.scalars(
            select(ApplicationUser)
            .outerjoin(ConsumerProfile)
            .where(
                ApplicationUser.status == "active",
                (
                    ApplicationUser.username.icontains(q_clean)
                    | ConsumerProfile.display_name.icontains(q_clean)
                ),
            )
            .limit(50)
        ).all()
        for u in users:
            artist_profile = u.artist_profile
            is_artist = artist_profile is not None
            display_name = (
                u.consumer_profile.display_name
                if u.consumer_profile and u.consumer_profile.display_name
                else (u.username or "")
            )
            results.append(
                SearchResultItem(
                    type="artist" if is_artist else "consumer",
                    handle=u.username or "",
                    display_name=display_name,
                    subtitle=artist_profile.role
                    if artist_profile
                    else (u.consumer_profile.bio if u.consumer_profile else None),
                )
            )

    if type is None or type == "pages":
        # Search pages
        pages = session.scalars(
            select(Page)
            .where(Page.slug.icontains(q_clean) | Page.display_name.icontains(q_clean))
            .limit(50)
        ).all()
        for p in pages:
            results.append(
                SearchResultItem(
                    type=p.page_type or "club",
                    handle=p.slug,
                    display_name=p.display_name,
                    subtitle=p.city,
                )
            )

    return results
