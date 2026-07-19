import base64
import binascii
import hashlib
import secrets
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Annotated, Any

from events.api.schemas import (
    AccountErasureRequest,
    AccountErasureResponse,
    CheckInRequest,
    CheckInResponse,
    CheckInTokenResponse,
    DoorStaffResponse,
    EventAccessResponse,
    EventBatchRequest,
    EventCreateRequest,
    EventFeedCandidatesRequest,
    EventListResponse,
    EventResponse,
    EventUpdateCreateRequest,
    EventUpdateListResponse,
    EventUpdateRequest,
    EventUpdateResponse,
    EventViewerContextResponse,
    GuestlistAddRequest,
    GuestlistEntryResponse,
    GuestQuotaRequest,
    GuestQuotaResponse,
    ManagerGuestlistEntryResponse,
    MentionTargetResponse,
    ViewerLineupArtistResponse,
)
from events.api.security import (
    CurrentUser,
    require_current_user,
    require_internal_token,
    require_write_quota,
)
from events.domain.models import (
    CheckInStatus,
    Event,
    EventAccessAuditLog,
    EventBoost,
    EventCheckInToken,
    EventDoorStaff,
    EventFollow,
    EventGuestlistEntry,
    EventGuestQuota,
    EventUpdate,
    GuestlistEntryStatus,
    LocationMode,
    utc_now,
)
from events.main_dependencies import get_db_session, settings
from events.settings import Settings
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import Select, String, and_, delete, false, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from events import media_client, social_client, users_client
from threshold_common.pagination import clamp_limit

router = APIRouter(dependencies=[Depends(require_internal_token)])
DbSession = Annotated[Session, Depends(get_db_session)]
CurrentPrincipal = Annotated[CurrentUser, Depends(require_current_user)]
WriteQuota = Annotated[None, Depends(require_write_quota)]

ALLOWED_ROLES = {"owner", "admin", "editor"}


def _canonical_location_mode(value: str) -> str:
    return LocationMode.public_location.value if value == "public" else value


def _reject_secret_location(value: object) -> None:
    if value == LocationMode.secret_location or value == LocationMode.secret_location.value:
        raise HTTPException(
            status_code=422,
            detail="secret_location flow is not implemented yet",
        )


def optional_viewer_id(
    user_id: Annotated[str | None, Header(alias="X-Threshold-User-Id")] = None,
) -> str | None:
    return user_id or None


ViewerId = Annotated[str | None, Depends(optional_viewer_id)]


def _clamp_limit(limit: int | None) -> int:
    return clamp_limit(limit, default=settings.default_list_limit, maximum=settings.max_list_limit)


def _encode_cursor(event: Event | None) -> str | None:
    if event is None:
        return None
    raw = f"{event.starts_at.isoformat()}|{event.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _encode_created_cursor(event: Event | None) -> str | None:
    if event is None:
        return None
    raw = f"{event.created_at.isoformat()}|{event.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _cursor_condition(before: str | None) -> ColumnElement[bool] | None:
    if not before:
        return None
    try:
        padded = before + "=" * (-len(before) % 4)
        raw_starts_at, raw_id = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        starts_at = datetime.fromisoformat(raw_starts_at)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc
    return or_(
        Event.starts_at < starts_at,
        and_(Event.starts_at == starts_at, Event.id < raw_id),
    )


def _created_cursor_condition(before: str | None) -> ColumnElement[bool] | None:
    if not before:
        return None
    try:
        padded = before + "=" * (-len(before) % 4)
        raw_created_at, raw_id = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        created_at = datetime.fromisoformat(raw_created_at)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc
    return or_(
        Event.created_at < created_at,
        and_(Event.created_at == created_at, Event.id < raw_id),
    )


def _events_response(
    session: Session,
    events: list[Event],
    viewer_id: str | None,
    *,
    follower_counts: dict[str, int] | None = None,
    boost_counts: dict[str, int] | None = None,
    enrich_lineup: bool = True,
    lineup_artist_refs: dict[str, dict[str, str]] | None = None,
    viewer_follows: set[str] | None = None,
    viewer_boosts: set[str] | None = None,
) -> list[EventResponse]:
    if not events:
        return []
    event_ids = [e.id for e in events]

    if follower_counts is None:
        follower_counts = defaultdict(int)
        for event_id, count in session.execute(
            select(EventFollow.event_id, func.count(EventFollow.id))
            .where(EventFollow.event_id.in_(event_ids))
            .group_by(EventFollow.event_id)
        ).all():
            follower_counts[event_id] = count

    if boost_counts is None:
        boost_counts = defaultdict(int)
        for event_id, count in session.execute(
            select(EventBoost.event_id, func.count(EventBoost.id))
            .where(EventBoost.event_id.in_(event_ids))
            .group_by(EventBoost.event_id)
        ).all():
            boost_counts[event_id] = count

    if viewer_id:
        if viewer_follows is None:
            viewer_follows = set(
                session.scalars(
                    select(EventFollow.event_id).where(
                        EventFollow.event_id.in_(event_ids),
                        EventFollow.user_id == viewer_id,
                    )
                ).all()
            )
        if viewer_boosts is None:
            viewer_boosts = set(
                session.scalars(
                    select(EventBoost.event_id).where(
                        EventBoost.event_id.in_(event_ids),
                        EventBoost.user_id == viewer_id,
                    )
                ).all()
            )
    else:
        viewer_follows = set()
        viewer_boosts = set()

    artist_refs = lineup_artist_refs or {}
    if enrich_lineup and lineup_artist_refs is None:
        artist_ids = list(
            dict.fromkeys(
                artist_id
                for event in events
                for item in event.lineup
                if isinstance(item, dict)
                if (artist_id := item.get("artist_profile_id"))
            )
        )[:100]
        artist_refs = users_client.get_artist_refs(
            settings,
            artist_ids,
        )

    return [
        EventResponse.model_validate(
            {
                **event.__dict__,
                "lineup": _enriched_lineup(event.lineup, artist_refs),
                "location_mode": _canonical_location_mode(event.location_mode),
                "venue_name": None
                if event.location_mode == LocationMode.secret_location.value
                else event.venue_name,
                "address": None
                if event.location_mode == LocationMode.secret_location.value
                else event.address,
                "boost_count": boost_counts.get(event.id, 0),
                "follower_count": follower_counts.get(event.id, 0),
                "is_following": (event.id in viewer_follows) if viewer_id else None,
                "is_boosting": (event.id in viewer_boosts) if viewer_id else None,
            }
        )
        for event in events
    ]


def _event_response(
    session: Session,
    event: Event,
    viewer_id: str | None,
    *,
    lineup_artist_refs: dict[str, dict[str, str]] | None = None,
) -> EventResponse:
    return _events_response(
        session,
        [event],
        viewer_id,
        lineup_artist_refs=lineup_artist_refs,
    )[0]


def _enriched_lineup(
    lineup: list[dict[str, str]], artist_refs: dict[str, dict[str, str]]
) -> list[dict[str, str]]:
    enriched: list[dict[str, str]] = []
    for item in lineup:
        artist_id = item.get("artist_profile_id")
        if not artist_id or artist_id not in artist_refs:
            enriched.append(item)
            continue
        ref = artist_refs[artist_id]
        enriched.append(
            {
                **item,
                "artist_handle": ref["username"],
                "display_name": ref["display_name"],
                "target_url": ref["target_url"],
            }
        )
    return enriched


def _validate_lineup_artist_refs(
    lineup: list[dict[str, str]],
) -> dict[str, dict[str, str]]:
    artist_ids = list(
        dict.fromkeys(
            artist_id
            for item in lineup
            if (artist_id := item.get("artist_profile_id"))
        )
    )
    if not artist_ids:
        return {}
    artist_refs = users_client.get_artist_refs(settings, artist_ids)
    if any(artist_id not in artist_refs for artist_id in artist_ids):
        raise HTTPException(status_code=422, detail="invalid lineup artist")
    return artist_refs


def _encode_update_cursor(update: EventUpdate | None) -> str | None:
    if update is None:
        return None
    raw = f"{update.created_at.isoformat()}|{update.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _update_cursor_condition(before: str | None) -> ColumnElement[bool] | None:
    if not before:
        return None
    try:
        padded = before + "=" * (-len(before) % 4)
        raw_created_at, raw_id = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        created_at = datetime.fromisoformat(raw_created_at)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc
    return or_(
        EventUpdate.created_at < created_at,
        and_(EventUpdate.created_at == created_at, EventUpdate.id < raw_id),
    )


def _event_update_response(event: Event, update: EventUpdate) -> EventUpdateResponse:
    return EventUpdateResponse(
        id=update.id,
        event_id=event.id,
        event_slug=event.slug,
        event_title=event.title,
        author_user_id=update.author_user_id,
        author_page_id=update.author_page_id,
        body=update.body,
        kind=update.kind,
        created_at=update.created_at,
        updated_at=update.updated_at,
    )


def _notify_event_followers(session: Session, event: Event, update: EventUpdate) -> None:
    follower_ids = session.scalars(
        select(EventFollow.user_id).where(
            EventFollow.event_id == event.id,
            EventFollow.user_id != update.author_user_id,
        )
    ).all()
    notification_body = update.body[:500]
    for recipient_user_id in follower_ids:
        users_client.notify_user(
            settings,
            recipient_user_id=recipient_user_id,
            actor_user_id=update.author_user_id,
            event_type="event.post.created",
            target_type="event_update",
            target_id=update.id,
            target_url=f"/events/{event.slug}",
            title=f"{event.title} update",
            body=notification_body,
            dedupe_key=f"event.post.created:{update.id}:{recipient_user_id}",
            metadata={
                "event_id": event.id,
                "event_slug": event.slug,
                "event_title": event.title,
                "event_update_id": update.id,
            },
        )


def _get_active_event(session: Session, slug: str) -> Event:
    event = session.scalar(select(Event).where(Event.slug == slug, Event.deleted_at.is_(None)))
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return event


def _validate_event_poster(asset_id: str | None, owner_user_id: str) -> None:
    if asset_id is None:
        return
    try:
        media_client.validate_event_poster_asset(
            settings, asset_id=asset_id, owner_user_id=owner_user_id
        )
    except media_client.MediaAssetValidationError as exc:
        raise HTTPException(status_code=422, detail="invalid poster media asset") from exc


def _announce_event_city_group(settings_obj: Settings, event: Event) -> bool:
    return social_client.announce_event(settings_obj, event)


@router.post("/v1/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> EventResponse:
    _reject_secret_location(payload.location_mode)
    role = users_client.check_page_role(settings, payload.page_id, user.user_id)
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="not authorized to manage this page")
    _validate_event_poster(payload.poster_media_asset_id, user.user_id)
    lineup_artist_refs = _validate_lineup_artist_refs(payload.lineup)
    event = Event(
        slug=payload.slug,
        title=payload.title,
        description=payload.description,
        starts_at=payload.starts_at,
        city=payload.city,
        location_mode=payload.location_mode,
        venue_name=payload.venue_name,
        address=payload.address,
        genres=payload.genres,
        lineup=payload.lineup,
        page_id=payload.page_id,
        created_by_user_id=user.user_id,
        poster_media_asset_id=payload.poster_media_asset_id,
    )
    session.add(event)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="event slug already exists") from exc
    session.refresh(event)
    _announce_event_city_group(settings, event)
    return _event_response(
        session,
        event,
        user.user_id,
        lineup_artist_refs=lineup_artist_refs,
    )


@router.patch("/v1/events/{slug}", response_model=EventResponse)
def update_event(
    slug: str,
    payload: EventUpdateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> EventResponse:
    event = _get_active_event(session, slug)
    role = users_client.check_page_role(settings, event.page_id, user.user_id)
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="not authorized to manage this page")
    updates = payload.model_dump(exclude_unset=True)
    if "location_mode" in updates:
        _reject_secret_location(updates["location_mode"])
    if "poster_media_asset_id" in updates:
        _validate_event_poster(updates["poster_media_asset_id"], user.user_id)
    lineup_artist_refs = None
    if "lineup" in updates:
        lineup_artist_refs = _validate_lineup_artist_refs(updates["lineup"])
    for field, value in updates.items():
        setattr(event, field, value)
    session.commit()
    session.refresh(event)
    return _event_response(
        session,
        event,
        user.user_id,
        lineup_artist_refs=lineup_artist_refs,
    )


@router.delete("/v1/events/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    slug: str,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> Response:
    event = _get_active_event(session, slug)
    role = users_client.check_page_role(settings, event.page_id, user.user_id)
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="not authorized to manage this page")
    event.deleted_at = utc_now()
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/v1/events", response_model=EventListResponse)
def list_events(
    session: DbSession,
    viewer_id: ViewerId = None,
    city: Annotated[str | None, Query()] = None,
    page_id: Annotated[str | None, Query()] = None,
    artist_profile_id: Annotated[str | None, Query(max_length=36)] = None,
    lineup_artist_user_id: Annotated[str | None, Query(max_length=36)] = None,
    q: Annotated[str | None, Query()] = None,
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
    sort: Annotated[str, Query(pattern="^(starts|created)$")] = "starts",
    upcoming: Annotated[bool, Query()] = False,
) -> EventListResponse:
    conditions: list[ColumnElement[bool]] = [Event.deleted_at.is_(None)]
    if upcoming:
        conditions.append(Event.starts_at >= utc_now())
    if city is not None:
        conditions.append(Event.city == city)
    if page_id is not None:
        conditions.append(Event.page_id == page_id)
    linked_artist_id = lineup_artist_user_id or artist_profile_id
    if linked_artist_id is not None:
        conditions.append(Event.lineup.cast(String).icontains(linked_artist_id))
    query = q.strip() if q else ""
    if query:
        conditions.append(
            or_(
                Event.slug.icontains(query),
                Event.title.icontains(query),
                Event.city.icontains(query),
                and_(
                    Event.location_mode != LocationMode.secret_location.value,
                    Event.venue_name.icontains(query),
                ),
                Event.description.icontains(query),
                Event.genres.cast(String).icontains(query),
                Event.lineup.cast(String).icontains(query),
            )
        )
    cursor_cond = None if upcoming else (
        _created_cursor_condition(before) if sort == "created" else _cursor_condition(before)
    )
    if cursor_cond is not None:
        conditions.append(cursor_cond)

    fetched_limit = _clamp_limit(limit)
    order_by = (Event.starts_at.asc(), Event.id.asc()) if upcoming else (
        (Event.created_at.desc(), Event.id.desc())
        if sort == "created"
        else (Event.starts_at.desc(), Event.id.desc())
    )
    rows = session.scalars(
        select(Event)
        .where(*conditions)
        .order_by(*order_by)
        .limit(fetched_limit + 1)
    ).all()
    visible = list(rows[:fetched_limit])
    next_before = None if upcoming else (
        _encode_created_cursor(visible[-1]) if sort == "created" else _encode_cursor(visible[-1])
    ) if len(rows) > fetched_limit and visible else None
    return EventListResponse(
        items=_events_response(session, visible, viewer_id),
        next_before=next_before,
    )


@router.post(
    "/internal/v1/events/feed-candidates",
    response_model=list[EventResponse],
)
def get_event_feed_candidates(
    payload: EventFeedCandidatesRequest,
    session: DbSession,
    viewer_id: ViewerId = None,
) -> list[EventResponse]:
    page_ids = list(dict.fromkeys(payload.followed_page_ids))
    creator_user_ids = list(dict.fromkeys(payload.followed_creator_user_ids))
    admission: list[ColumnElement[bool]] = []
    if payload.city is not None:
        admission.append(func.lower(Event.city) == payload.city.lower())
    if page_ids:
        admission.append(Event.page_id.in_(page_ids))
    if creator_user_ids:
        admission.append(Event.created_by_user_id.in_(creator_user_ids))
    viewer_follow: ColumnElement[bool] = false()
    viewer_boost: ColumnElement[bool] = false()
    if viewer_id:
        viewer_follow = (
            select(EventFollow.id)
            .where(
                EventFollow.event_id == Event.id,
                EventFollow.user_id == viewer_id,
            )
            .exists()
        )
        viewer_boost = (
            select(EventBoost.id)
            .where(
                EventBoost.event_id == Event.id,
                EventBoost.user_id == viewer_id,
            )
            .exists()
        )
        admission.append(viewer_follow)
    if not admission:
        return []

    follower_count = (
        select(func.count(EventFollow.id))
        .where(EventFollow.event_id == Event.id)
        .correlate(Event)
        .scalar_subquery()
    )
    boost_count = (
        select(func.count(EventBoost.id))
        .where(EventBoost.event_id == Event.id)
        .correlate(Event)
        .scalar_subquery()
    )
    rows = session.execute(
        select(Event, follower_count, boost_count, viewer_follow, viewer_boost)
        .where(Event.deleted_at.is_(None), or_(*admission))
        .order_by(Event.created_at.desc(), Event.id.desc())
        .limit(payload.limit)
    ).tuples().all()
    events = [event for event, _, _, _, _ in rows]
    return _events_response(
        session,
        events,
        viewer_id,
        follower_counts={event.id: followers for event, followers, _, _, _ in rows},
        boost_counts={event.id: boosts for event, _, boosts, _, _ in rows},
        enrich_lineup=False,
        viewer_follows={
            event.id for event, _, _, is_following, _ in rows if is_following
        },
        viewer_boosts={
            event.id for event, _, _, _, is_boosting in rows if is_boosting
        },
    )


@router.post("/internal/v1/events/batch", response_model=list[EventResponse])
def get_events_batch(payload: EventBatchRequest, session: DbSession) -> list[EventResponse]:
    slugs = list(dict.fromkeys(payload.slugs))
    if not slugs:
        return []
    follower_count = (
        select(func.count(EventFollow.id))
        .where(EventFollow.event_id == Event.id)
        .correlate(Event)
        .scalar_subquery()
    )
    boost_count = (
        select(func.count(EventBoost.id))
        .where(EventBoost.event_id == Event.id)
        .correlate(Event)
        .scalar_subquery()
    )
    rows = session.execute(
        select(Event, follower_count, boost_count).where(
            Event.slug.in_(slugs),
            Event.deleted_at.is_(None),
        )
    ).tuples().all()
    events = {event.slug: event for event, _, _ in rows}
    ordered = [events[slug] for slug in slugs if slug in events]
    return _events_response(
        session,
        ordered,
        None,
        follower_counts={event.id: followers for event, followers, _ in rows},
        boost_counts={event.id: boosts for event, _, boosts in rows},
        enrich_lineup=False,
    )


@router.post("/internal/v1/account-erasure", response_model=AccountErasureResponse)
def erase_account_data(
    payload: AccountErasureRequest,
    session: DbSession,
) -> AccountErasureResponse:
    user_id = payload.user_id
    anonymous_user_id = "deleted-user"

    def scrub_user_id(value: Any) -> Any:
        if value == user_id:
            return None
        if isinstance(value, dict):
            return {key: scrub_user_id(item) for key, item in value.items()}
        if isinstance(value, list):
            return [scrub_user_id(item) for item in value]
        return value

    session.execute(delete(EventFollow).where(EventFollow.user_id == user_id))
    session.execute(delete(EventBoost).where(EventBoost.user_id == user_id))
    session.execute(
        delete(EventGuestlistEntry).where(EventGuestlistEntry.guest_user_id == user_id)
    )
    session.execute(delete(EventDoorStaff).where(EventDoorStaff.user_id == user_id))

    session.execute(
        update(Event)
        .where(Event.created_by_user_id == user_id)
        .values(created_by_user_id=anonymous_user_id)
    )
    session.execute(
        update(EventUpdate)
        .where(EventUpdate.author_user_id == user_id)
        .values(author_user_id=anonymous_user_id)
    )
    session.execute(
        update(EventGuestlistEntry)
        .where(EventGuestlistEntry.added_by_user_id == user_id)
        .values(added_by_user_id=anonymous_user_id)
    )
    session.execute(
        update(EventGuestlistEntry)
        .where(EventGuestlistEntry.checked_in_by_user_id == user_id)
        .values(checked_in_by_user_id=None)
    )
    session.execute(
        update(EventGuestQuota)
        .where(EventGuestQuota.assigned_by_user_id == user_id)
        .values(assigned_by_user_id=anonymous_user_id)
    )
    session.execute(
        update(EventDoorStaff)
        .where(EventDoorStaff.assigned_by_user_id == user_id)
        .values(assigned_by_user_id=anonymous_user_id)
    )
    session.execute(
        update(EventAccessAuditLog)
        .where(EventAccessAuditLog.actor_user_id == user_id)
        .values(actor_user_id=None)
    )
    session.execute(
        update(EventAccessAuditLog)
        .where(EventAccessAuditLog.target_id == user_id)
        .values(target_id=anonymous_user_id)
    )
    for audit_log in session.scalars(select(EventAccessAuditLog)):
        scrubbed = scrub_user_id(audit_log.metadata_json)
        if scrubbed != audit_log.metadata_json:
            audit_log.metadata_json = scrubbed

    session.commit()
    return AccountErasureResponse()


@router.get("/v1/events/{slug}", response_model=EventResponse)
def get_event(slug: str, session: DbSession, viewer_id: ViewerId = None) -> EventResponse:
    event = _get_active_event(session, slug)
    return _event_response(session, event, viewer_id)


@router.get("/v1/event-updates", response_model=EventUpdateListResponse)
def list_all_event_updates(
    session: DbSession,
    page_id: Annotated[str | None, Query()] = None,
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> EventUpdateListResponse:
    conditions: list[ColumnElement[bool]] = [
        Event.deleted_at.is_(None),
        EventUpdate.deleted_at.is_(None),
    ]
    if page_id is not None:
        conditions.append(EventUpdate.author_page_id == page_id)
    cursor_cond = _update_cursor_condition(before)
    if cursor_cond is not None:
        conditions.append(cursor_cond)
    fetched_limit = _clamp_limit(limit)
    rows = session.execute(
        select(Event, EventUpdate)
        .join(EventUpdate, EventUpdate.event_id == Event.id)
        .where(*conditions)
        .order_by(EventUpdate.created_at.desc(), EventUpdate.id.desc())
        .limit(fetched_limit + 1)
    ).all()
    visible = list(rows[:fetched_limit])
    next_before = (
        _encode_update_cursor(visible[-1][1]) if len(rows) > fetched_limit and visible else None
    )
    return EventUpdateListResponse(
        items=[_event_update_response(event, update) for event, update in visible],
        next_before=next_before,
    )


@router.post(
    "/v1/events/{slug}/updates",
    response_model=EventUpdateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event_update(
    slug: str,
    payload: EventUpdateCreateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> EventUpdateResponse:
    event = _get_active_event(session, slug)
    role = users_client.check_page_role(settings, event.page_id, user.user_id)
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="not authorized to update this event")
    update = EventUpdate(
        event_id=event.id,
        author_user_id=user.user_id,
        author_page_id=event.page_id,
        body=payload.body,
    )
    session.add(update)
    session.commit()
    session.refresh(update)
    _notify_event_followers(session, event, update)
    return _event_update_response(event, update)


@router.get("/v1/events/{slug}/updates", response_model=EventUpdateListResponse)
def list_event_updates(
    slug: str,
    session: DbSession,
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> EventUpdateListResponse:
    event = _get_active_event(session, slug)
    conditions: list[ColumnElement[bool]] = [
        EventUpdate.event_id == event.id,
        EventUpdate.deleted_at.is_(None),
    ]
    cursor_cond = _update_cursor_condition(before)
    if cursor_cond is not None:
        conditions.append(cursor_cond)
    fetched_limit = _clamp_limit(limit)
    rows = session.scalars(
        select(EventUpdate)
        .where(*conditions)
        .order_by(EventUpdate.created_at.desc(), EventUpdate.id.desc())
        .limit(fetched_limit + 1)
    ).all()
    visible = list(rows[:fetched_limit])
    next_before = (
        _encode_update_cursor(visible[-1]) if len(rows) > fetched_limit and visible else None
    )
    return EventUpdateListResponse(
        items=[_event_update_response(event, update) for update in visible],
        next_before=next_before,
    )


@router.get("/internal/v1/mention-targets/events/{slug}", response_model=MentionTargetResponse)
def resolve_event_mention_target(slug: str, session: DbSession) -> MentionTargetResponse:
    event = _get_active_event(session, slug)
    return MentionTargetResponse(
        target_type="event",
        target_id=event.id,
        handle=event.slug,
        display_name=event.title,
        target_url=f"/events/{event.slug}",
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=utc_now().tzinfo)
    return expires_at < utc_now()


def _guestlist_entry_response(event: Event, entry: EventGuestlistEntry) -> GuestlistEntryResponse:
    return GuestlistEntryResponse(
        id=entry.id,
        event_id=event.id,
        event_slug=event.slug,
        guest_user_id=entry.guest_user_id,
        guest_display_name=entry.guest_display_name,
        user_id=entry.guest_user_id,
        username=entry.guest_username,
        display_name=entry.guest_display_name,
        source="dj" if entry.added_by_artist_profile_id else "organizer",
        added_by_user_id=entry.added_by_user_id,
        added_by_artist_profile_id=entry.added_by_artist_profile_id,
        status=entry.status,
        checked_in_at=entry.checked_in_at,
        checked_in_by_user_id=entry.checked_in_by_user_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _manager_guestlist_entry_response(
    entry: EventGuestlistEntry,
) -> ManagerGuestlistEntryResponse:
    return ManagerGuestlistEntryResponse(
        id=entry.id,
        guest_user_id=entry.guest_user_id,
        username=entry.guest_username,
        display_name=entry.guest_display_name,
        source="dj" if entry.added_by_artist_profile_id else "organizer",
        status=GuestlistEntryStatus(entry.status),
        checked_in_at=entry.checked_in_at,
    )


def _require_lineup_artist(event: Event, artist_profile_id: str) -> None:
    if not any(item.get("artist_profile_id") == artist_profile_id for item in event.lineup):
        raise HTTPException(status_code=403, detail="artist is not in event lineup")


def _quota_response(session: Session, event: Event, quota: EventGuestQuota) -> GuestQuotaResponse:
    used = session.scalar(
        select(func.count(EventGuestlistEntry.id)).where(
            EventGuestlistEntry.event_id == event.id,
            EventGuestlistEntry.added_by_artist_profile_id == quota.artist_profile_id,
            EventGuestlistEntry.status == GuestlistEntryStatus.active.value,
        )
    ) or 0
    return GuestQuotaResponse(
        id=quota.id,
        event_id=event.id,
        event_slug=event.slug,
        artist_profile_id=quota.artist_profile_id,
        quota=quota.quota,
        used=used,
        remaining=max(0, quota.quota - used),
    )


def _quota_summaries(session: Session, event: Event) -> list[GuestQuotaResponse]:
    used = (
        select(
            EventGuestlistEntry.added_by_artist_profile_id.label("artist_profile_id"),
            func.count(EventGuestlistEntry.id).label("used"),
        )
        .where(
            EventGuestlistEntry.event_id == event.id,
            EventGuestlistEntry.added_by_artist_profile_id.is_not(None),
            EventGuestlistEntry.status == GuestlistEntryStatus.active.value,
        )
        .group_by(EventGuestlistEntry.added_by_artist_profile_id)
        .subquery()
    )
    rows = session.execute(
        select(EventGuestQuota, func.coalesce(used.c.used, 0))
        .outerjoin(used, EventGuestQuota.artist_profile_id == used.c.artist_profile_id)
        .where(EventGuestQuota.event_id == event.id)
        .order_by(EventGuestQuota.artist_profile_id.asc())
    ).all()
    return [
        GuestQuotaResponse(
            id=quota.id,
            event_id=event.id,
            event_slug=event.slug,
            artist_profile_id=quota.artist_profile_id,
            quota=quota.quota,
            used=count,
            remaining=max(0, quota.quota - count),
        )
        for quota, count in rows
    ]


def _require_event_manager(event: Event, user_id: str) -> None:
    role = users_client.check_page_role(settings, event.page_id, user_id)
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="not authorized to manage this event")


def _door_staff_lock_query(
    event_id: str,
    *,
    user_id: str | None = None,
    assignment_id: str | None = None,
) -> Select[tuple[EventDoorStaff]]:
    query = select(EventDoorStaff).where(EventDoorStaff.event_id == event_id)
    if user_id is not None:
        query = query.where(EventDoorStaff.user_id == user_id)
    if assignment_id is not None:
        query = query.where(EventDoorStaff.id == assignment_id)
    return query.with_for_update()


def _require_check_in_access(session: Session, event: Event, user_id: str) -> None:
    role = users_client.check_page_role(settings, event.page_id, user_id)
    if role in ALLOWED_ROLES:
        return
    door_staff = session.scalar(_door_staff_lock_query(event.id, user_id=user_id))
    if door_staff is None or user_id not in users_client.get_active_user_refs(
        settings, [user_id]
    ):
        raise HTTPException(status_code=403, detail="not authorized to check in guests")


def _door_staff_response(
    door_staff: EventDoorStaff, user_ref: dict[str, str] | None
) -> DoorStaffResponse:
    return DoorStaffResponse(
        id=door_staff.id,
        username=user_ref["username"] if user_ref else None,
        display_name=user_ref["display_name"] if user_ref else None,
        assigned_at=door_staff.assigned_at,
    )


@router.get(
    "/v1/events/{slug}/viewer-context",
    response_model=EventViewerContextResponse,
)
def get_event_viewer_context(
    slug: str, user: CurrentPrincipal, session: DbSession
) -> EventViewerContextResponse:
    event = _get_active_event(session, slug)
    is_manager = (
        users_client.check_page_role(settings, event.page_id, user.user_id) in ALLOWED_ROLES
    )
    guest_entry, door_staff_id = session.execute(
        select(EventGuestlistEntry, EventDoorStaff.id)
        .select_from(Event)
        .outerjoin(
            EventGuestlistEntry,
            and_(
                EventGuestlistEntry.event_id == Event.id,
                EventGuestlistEntry.guest_user_id == user.user_id,
                EventGuestlistEntry.status == GuestlistEntryStatus.active.value,
            ),
        )
        .outerjoin(
            EventDoorStaff,
            and_(
                EventDoorStaff.event_id == Event.id,
                EventDoorStaff.user_id == user.user_id,
            ),
        )
        .where(Event.id == event.id)
    ).one()
    can_check_in = is_manager or (
        door_staff_id is not None
        and user.user_id
        in users_client.get_active_user_refs(settings, [user.user_id])
    )
    quota_summaries = _quota_summaries(session, event)
    quotas_by_artist = {quota.artist_profile_id: quota for quota in quota_summaries}
    lineup_artist_ids = list(
        dict.fromkeys(
            artist_id
            for item in event.lineup
            if isinstance(item, dict)
            if (artist_id := item.get("artist_profile_id"))
        )
    )
    artist_refs = users_client.get_artist_refs(settings, lineup_artist_ids)
    viewer_lineup_artists = []
    for artist_profile_id in lineup_artist_ids:
        artist = artist_refs.get(artist_profile_id)
        if artist and (artist.get("owner_user_id") or artist.get("user_id")) == user.user_id:
            viewer_lineup_artists.append(
                ViewerLineupArtistResponse(
                    artist_profile_id=artist_profile_id,
                    quota=quotas_by_artist.get(artist_profile_id),
                )
            )

    active_guest_access = (
        EventAccessResponse(
            event_id=event.id,
            event_slug=event.slug,
            user_id=user.user_id,
            status=GuestlistEntryStatus(guest_entry.status),
            can_check_in=guest_entry.checked_in_at is None,
            checked_in_at=guest_entry.checked_in_at,
        )
        if guest_entry
        else None
    )
    return EventViewerContextResponse(
        event_id=event.id,
        event_slug=event.slug,
        active_guest_access=active_guest_access,
        can_mint_qr=guest_entry is not None and guest_entry.checked_in_at is None,
        can_manage_guestlist=is_manager,
        can_set_dj_quota=is_manager,
        can_check_in=can_check_in,
        can_post_update=is_manager,
        viewer_lineup_artists=viewer_lineup_artists,
        quota_summaries=quota_summaries if is_manager else [],
    )


@router.get("/v1/events/{slug}/guestlist", response_model=list[ManagerGuestlistEntryResponse])
def list_guestlist(
    slug: str, user: CurrentPrincipal, session: DbSession
) -> list[ManagerGuestlistEntryResponse]:
    event = _get_active_event(session, slug)
    _require_event_manager(event, user.user_id)
    entries = session.scalars(
        select(EventGuestlistEntry)
        .where(EventGuestlistEntry.event_id == event.id)
        .order_by(EventGuestlistEntry.created_at.asc(), EventGuestlistEntry.id.asc())
    ).all()
    return [_manager_guestlist_entry_response(entry) for entry in entries]


def _write_access_audit(
    session: Session,
    event: Event,
    *,
    actor_user_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict[str, str | int | bool | None] | None = None,
) -> None:
    session.add(
        EventAccessAuditLog(
            event_id=event.id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata or {},
        )
    )


@router.get("/v1/events/{slug}/door-staff", response_model=list[DoorStaffResponse])
def list_door_staff(
    slug: str, user: CurrentPrincipal, session: DbSession
) -> list[DoorStaffResponse]:
    event = _get_active_event(session, slug)
    _require_event_manager(event, user.user_id)
    rows = session.scalars(
        select(EventDoorStaff)
        .where(EventDoorStaff.event_id == event.id)
        .order_by(EventDoorStaff.assigned_at.asc(), EventDoorStaff.id.asc())
    ).all()
    refs = users_client.get_active_user_refs(settings, [row.user_id for row in rows])
    return [_door_staff_response(row, refs.get(row.user_id)) for row in rows]


def _get_or_create_door_staff(
    session: Session,
    *,
    event_id: str,
    user_id: str,
    assigned_by_user_id: str,
) -> tuple[EventDoorStaff, bool]:
    existing = session.scalar(
        select(EventDoorStaff).where(
            EventDoorStaff.event_id == event_id,
            EventDoorStaff.user_id == user_id,
        )
    )
    if existing is not None:
        return existing, False
    door_staff = EventDoorStaff(
        event_id=event_id,
        user_id=user_id,
        assigned_by_user_id=assigned_by_user_id,
    )
    try:
        with session.begin_nested():
            session.add(door_staff)
            session.flush()
    except IntegrityError as exc:
        existing = session.scalar(
            select(EventDoorStaff).where(
                EventDoorStaff.event_id == event_id,
                EventDoorStaff.user_id == user_id,
            )
        )
        if existing is None:
            raise HTTPException(status_code=409, detail="door staff assignment conflict") from exc
        return existing, False
    return door_staff, True


@router.put(
    "/v1/events/{slug}/door-staff/by-username/{door_username}",
    response_model=DoorStaffResponse,
)
def assign_door_staff(
    slug: str,
    door_username: str,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> DoorStaffResponse:
    event = _get_active_event(session, slug)
    _require_event_manager(event, user.user_id)
    resolved = users_client.get_user_by_username(settings, door_username)
    if resolved is None:
        raise HTTPException(status_code=404, detail="user not found")
    door_staff, created = _get_or_create_door_staff(
        session,
        event_id=event.id,
        user_id=resolved["user_id"],
        assigned_by_user_id=user.user_id,
    )
    if created:
        _write_access_audit(
            session,
            event,
            actor_user_id=user.user_id,
            action="door_staff.assigned",
            target_type="event_door_staff",
            target_id=door_staff.id,
            metadata={"user_id": door_staff.user_id},
        )
        session.commit()
        session.refresh(door_staff)
    return _door_staff_response(door_staff, resolved)


@router.delete("/v1/events/{slug}/door-staff/{assignment_id}", status_code=204)
def revoke_door_staff(
    slug: str,
    assignment_id: str,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> Response:
    event = _get_active_event(session, slug)
    _require_event_manager(event, user.user_id)
    door_staff = session.scalar(
        _door_staff_lock_query(event.id, assignment_id=assignment_id)
    )
    if door_staff is None:
        return Response(status_code=204)
    _write_access_audit(
        session,
        event,
        actor_user_id=user.user_id,
        action="door_staff.revoked",
        target_type="event_door_staff",
        target_id=door_staff.id,
        metadata={"user_id": door_staff.user_id},
    )
    session.delete(door_staff)
    session.commit()
    return Response(status_code=204)


def _revoke_issued_check_in_tokens(session: Session, *, guestlist_entry_id: str) -> None:
    session.execute(
        update(EventCheckInToken)
        .where(
            EventCheckInToken.guestlist_entry_id == guestlist_entry_id,
            EventCheckInToken.status == CheckInStatus.issued.value,
        )
        .values(status=CheckInStatus.revoked.value)
    )


def _guestlist_entry_lock_query(
    event_id: str,
    guest_user_id: str,
    *,
    active_only: bool = True,
) -> Select[tuple[EventGuestlistEntry]]:
    query = select(EventGuestlistEntry).where(
        EventGuestlistEntry.event_id == event_id,
        EventGuestlistEntry.guest_user_id == guest_user_id,
    )
    if active_only:
        query = query.where(
            EventGuestlistEntry.status == GuestlistEntryStatus.active.value
        )
    return query.with_for_update()


def _claim_check_in_token(session: Session, *, token_id: str, used_at: datetime) -> bool:
    result = session.connection().execute(
        update(EventCheckInToken)
        .where(
            EventCheckInToken.id == token_id,
            EventCheckInToken.status == CheckInStatus.issued.value,
        )
        .values(status=CheckInStatus.used.value, used_at=used_at)
    )
    return result.rowcount == 1


def _claim_guestlist_entry(
    session: Session,
    *,
    entry_id: str,
    checked_in_by_user_id: str,
    checked_in_at: datetime,
) -> bool:
    result = session.connection().execute(
        update(EventGuestlistEntry)
        .where(
            EventGuestlistEntry.id == entry_id,
            EventGuestlistEntry.status == GuestlistEntryStatus.active.value,
            EventGuestlistEntry.checked_in_at.is_(None),
        )
        .values(
            checked_in_at=checked_in_at,
            checked_in_by_user_id=checked_in_by_user_id,
        )
    )
    return result.rowcount == 1


def _require_artist_quota(
    session: Session, event: Event, artist_profile_id: str, user_id: str, guest_user_id: str
) -> None:
    _require_lineup_artist(event, artist_profile_id)
    artist = users_client.get_artist_ref(settings, artist_profile_id)
    if artist is None:
        raise HTTPException(status_code=404, detail="artist profile not found")
    if (artist.get("owner_user_id") or artist.get("user_id")) != user_id:
        raise HTTPException(status_code=403, detail="artist profile owner required")
    quota = session.scalar(
        select(EventGuestQuota)
        .where(
            EventGuestQuota.event_id == event.id,
            EventGuestQuota.artist_profile_id == artist_profile_id,
        )
        .with_for_update()
    )
    if quota is None:
        raise HTTPException(status_code=403, detail="guest quota not assigned")
    used = session.scalar(
        select(func.count(EventGuestlistEntry.id)).where(
            EventGuestlistEntry.event_id == event.id,
            EventGuestlistEntry.added_by_artist_profile_id == artist_profile_id,
            EventGuestlistEntry.status == GuestlistEntryStatus.active.value,
            EventGuestlistEntry.guest_user_id != guest_user_id,
        )
    ) or 0
    if used >= quota.quota:
        raise HTTPException(status_code=409, detail="guest quota exhausted")


@router.put(
    "/v1/events/{slug}/guestlist/quotas/{artist_profile_id}",
    response_model=GuestQuotaResponse,
)
def set_guest_quota(
    slug: str,
    artist_profile_id: str,
    payload: GuestQuotaRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> GuestQuotaResponse:
    event = _get_active_event(session, slug)
    _require_event_manager(event, user.user_id)
    _require_lineup_artist(event, artist_profile_id)
    if users_client.get_artist_ref(settings, artist_profile_id) is None:
        raise HTTPException(status_code=404, detail="artist profile not found")
    quota = session.scalar(
        select(EventGuestQuota).where(
            EventGuestQuota.event_id == event.id,
            EventGuestQuota.artist_profile_id == artist_profile_id,
        )
    )
    if quota is None:
        quota = EventGuestQuota(
            event_id=event.id,
            artist_profile_id=artist_profile_id,
            assigned_by_user_id=user.user_id,
            quota=payload.quota,
        )
    else:
        quota.quota = payload.quota
        quota.assigned_by_user_id = user.user_id
    session.add(quota)
    _write_access_audit(
        session,
        event,
        actor_user_id=user.user_id,
        action="guest_quota.set",
        target_type="artist_profile",
        target_id=artist_profile_id,
        metadata={"quota": payload.quota},
    )
    session.commit()
    session.refresh(quota)
    return _quota_response(session, event, quota)


@router.put(
    "/v1/events/{slug}/guest-quotas/{artist_profile_id}",
    response_model=GuestQuotaResponse,
)
def set_guest_quota_alias(
    slug: str,
    artist_profile_id: str,
    payload: GuestQuotaRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> GuestQuotaResponse:
    return set_guest_quota(slug, artist_profile_id, payload, user, _, session)


@router.post("/v1/events/{slug}/guestlist", response_model=GuestlistEntryResponse, status_code=201)
def add_guestlist_entry(
    slug: str,
    payload: GuestlistAddRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> GuestlistEntryResponse:
    event = _get_active_event(session, slug)
    guest_user_id = payload.resolved_user_id
    if not guest_user_id:
        raise HTTPException(status_code=422, detail="guest user id required")
    entry = session.scalar(
        _guestlist_entry_lock_query(
            event.id,
            guest_user_id,
            active_only=False,
        )
    )
    if payload.artist_profile_id:
        _require_artist_quota(
            session, event, payload.artist_profile_id, user.user_id, guest_user_id
        )
    else:
        _require_event_manager(event, user.user_id)
    if entry is None:
        entry = EventGuestlistEntry(
            event_id=event.id,
            guest_user_id=guest_user_id,
            guest_username=payload.username,
            guest_display_name=payload.resolved_display_name,
            added_by_user_id=user.user_id,
            added_by_artist_profile_id=payload.artist_profile_id,
        )
    else:
        _revoke_issued_check_in_tokens(session, guestlist_entry_id=entry.id)
        entry.guest_username = payload.username
        entry.guest_display_name = payload.resolved_display_name
        entry.added_by_user_id = user.user_id
        entry.added_by_artist_profile_id = payload.artist_profile_id
        entry.status = GuestlistEntryStatus.active.value
        entry.checked_in_at = None
        entry.checked_in_by_user_id = None
    session.add(entry)
    session.flush()
    _write_access_audit(
        session,
        event,
        actor_user_id=user.user_id,
        action="guestlist.added",
        target_type="event_guestlist",
        target_id=entry.id,
        metadata={
            "guest_user_id": entry.guest_user_id,
            "source": "dj" if entry.added_by_artist_profile_id else "organizer",
        },
    )
    users_client.notify_user(
        settings,
        recipient_user_id=entry.guest_user_id,
        actor_user_id=user.user_id,
        event_type="guestlist.added",
        target_type="event_guestlist",
        target_id=entry.id,
        target_url=f"/events/{event.slug}",
        title=f"You are on the guestlist for {event.title}",
        body=None,
        dedupe_key=f"guestlist.added:{entry.id}:{entry.guest_user_id}",
        metadata={
            "event_id": event.id,
            "event_slug": event.slug,
            "event_title": event.title,
            "access_state": "approved",
        },
    )
    session.commit()
    session.refresh(entry)
    return _guestlist_entry_response(event, entry)


@router.post(
    "/v1/events/{slug}/guestlist/dj",
    response_model=GuestlistEntryResponse,
    status_code=201,
)
def add_dj_guestlist_entry(
    slug: str,
    payload: GuestlistAddRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> GuestlistEntryResponse:
    if not payload.artist_profile_id:
        raise HTTPException(status_code=422, detail="artist profile id required")
    return add_guestlist_entry(slug, payload, user, _, session)


@router.get("/v1/events/{slug}/access", response_model=EventAccessResponse)
def get_event_access(slug: str, user: CurrentPrincipal, session: DbSession) -> EventAccessResponse:
    event = _get_active_event(session, slug)
    entry = session.scalar(
        select(EventGuestlistEntry).where(
            EventGuestlistEntry.event_id == event.id,
            EventGuestlistEntry.guest_user_id == user.user_id,
            EventGuestlistEntry.status == GuestlistEntryStatus.active.value,
        )
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="guestlist access not found")
    return EventAccessResponse(
        event_id=event.id,
        event_slug=event.slug,
        user_id=user.user_id,
        status=GuestlistEntryStatus(entry.status),
        can_check_in=entry.checked_in_at is None,
        checked_in_at=entry.checked_in_at,
    )


@router.delete("/v1/events/{slug}/guestlist/{guest_user_id}", status_code=204)
def remove_guestlist_entry(
    slug: str,
    guest_user_id: str,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> Response:
    event = _get_active_event(session, slug)
    _require_event_manager(event, user.user_id)
    entry = session.scalar(_guestlist_entry_lock_query(event.id, guest_user_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="guestlist entry not found")
    entry.status = GuestlistEntryStatus.removed.value
    _revoke_issued_check_in_tokens(session, guestlist_entry_id=entry.id)
    session.add(entry)
    _write_access_audit(
        session,
        event,
        actor_user_id=user.user_id,
        action="guestlist.removed",
        target_type="event_guestlist",
        target_id=entry.id,
        metadata={"guest_user_id": entry.guest_user_id},
    )
    users_client.notify_user(
        settings,
        recipient_user_id=entry.guest_user_id,
        actor_user_id=user.user_id,
        event_type="guestlist.removed",
        target_type="event_guestlist",
        target_id=entry.id,
        target_url=f"/events/{event.slug}",
        title=f"Guestlist access removed for {event.title}",
        body=None,
        dedupe_key=f"guestlist.removed:{entry.id}:{entry.guest_user_id}",
        metadata={
            "event_id": event.id,
            "event_slug": event.slug,
            "event_title": event.title,
            "access_state": "rejected",
        },
    )
    session.commit()
    return Response(status_code=204)


@router.post(
    "/v1/events/{slug}/guestlist/me/qr-token",
    response_model=CheckInTokenResponse,
    status_code=201,
)
def create_guest_check_in_token(
    slug: str,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> CheckInTokenResponse:
    event = _get_active_event(session, slug)
    entry = session.scalar(_guestlist_entry_lock_query(event.id, user.user_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="guestlist access not found")
    if entry.checked_in_at is not None:
        raise HTTPException(status_code=409, detail="guest already checked in")
    _revoke_issued_check_in_tokens(session, guestlist_entry_id=entry.id)
    token_value = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(seconds=settings.check_in_token_ttl_seconds)
    session.add(
        EventCheckInToken(
            event_id=event.id,
            guestlist_entry_id=entry.id,
            token_hash=_token_hash(token_value),
            expires_at=expires_at,
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="check-in token mint conflict") from exc
    return CheckInTokenResponse(token=token_value, expires_at=expires_at)


@router.post(
    "/v1/events/{slug}/check-in-tokens",
    response_model=CheckInTokenResponse,
    status_code=201,
)
def create_guest_check_in_token_alias(
    slug: str,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> CheckInTokenResponse:
    return create_guest_check_in_token(slug, user, _, session)


@router.post("/v1/events/{slug}/check-in", response_model=CheckInResponse)
def check_in_guest(
    slug: str,
    payload: CheckInRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> CheckInResponse:
    event = _get_active_event(session, slug)
    _require_check_in_access(session, event, user.user_id)
    token = session.scalar(
        select(EventCheckInToken).where(
            EventCheckInToken.event_id == event.id,
            EventCheckInToken.token_hash == _token_hash(payload.token),
        )
    )
    if token is None or _is_expired(token.expires_at):
        raise HTTPException(status_code=404, detail="check-in token not found")
    if token.status != CheckInStatus.issued.value:
        raise HTTPException(status_code=409, detail="check-in token already used")
    entry = session.get(EventGuestlistEntry, token.guestlist_entry_id)
    if entry is None or entry.status != GuestlistEntryStatus.active.value:
        raise HTTPException(status_code=404, detail="guestlist access not found")
    now = utc_now()
    if not _claim_guestlist_entry(
        session,
        entry_id=entry.id,
        checked_in_by_user_id=user.user_id,
        checked_in_at=now,
    ):
        session.rollback()
        raise HTTPException(status_code=409, detail="guest already checked in")
    if not _claim_check_in_token(session, token_id=token.id, used_at=now):
        session.rollback()
        raise HTTPException(status_code=409, detail="check-in token already used")
    _revoke_issued_check_in_tokens(session, guestlist_entry_id=entry.id)
    _write_access_audit(
        session,
        event,
        actor_user_id=user.user_id,
        action="guestlist.checked_in",
        target_type="event_guestlist",
        target_id=entry.id,
        metadata={"guest_user_id": entry.guest_user_id},
    )
    session.commit()
    return CheckInResponse(
        status="checked_in",
        display_name=entry.guest_display_name,
        username=entry.guest_username,
    )


@router.post("/v1/events/{slug}/check-ins/validate", response_model=CheckInResponse)
def check_in_guest_alias(
    slug: str,
    payload: CheckInRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> CheckInResponse:
    return check_in_guest(slug, payload, user, _, session)


@router.post("/v1/events/{slug}/follow", response_model=EventResponse)
def follow_event(
    slug: str, user: CurrentPrincipal, _: WriteQuota, session: DbSession
) -> EventResponse:
    event = _get_active_event(session, slug)
    session.add(EventFollow(event_id=event.id, user_id=user.user_id))
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="already following") from exc
    session.refresh(event)
    return _event_response(session, event, user.user_id)


@router.delete("/v1/events/{slug}/follow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_event(
    slug: str, user: CurrentPrincipal, _: WriteQuota, session: DbSession, response: Response
) -> Response:
    event = _get_active_event(session, slug)
    follow = session.scalar(
        select(EventFollow).where(
            EventFollow.event_id == event.id, EventFollow.user_id == user.user_id
        )
    )
    if follow is not None:
        session.delete(follow)
        session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/v1/events/{slug}/boost", response_model=EventResponse)
def boost_event(
    slug: str, user: CurrentPrincipal, _: WriteQuota, session: DbSession
) -> EventResponse:
    event = _get_active_event(session, slug)
    session.add(EventBoost(event_id=event.id, user_id=user.user_id))
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="already boosting") from exc
    session.refresh(event)
    return _event_response(session, event, user.user_id)


@router.delete("/v1/events/{slug}/boost", status_code=status.HTTP_204_NO_CONTENT)
def unboost_event(
    slug: str, user: CurrentPrincipal, _: WriteQuota, session: DbSession, response: Response
) -> Response:
    event = _get_active_event(session, slug)
    boost = session.scalar(
        select(EventBoost).where(
            EventBoost.event_id == event.id, EventBoost.user_id == user.user_id
        )
    )
    if boost is not None:
        session.delete(boost)
        session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
