from collections import defaultdict
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from social.api.schemas import (
    AnonymizeAuthorRequest,
    BlockCreateRequest,
    BlockResponse,
    CommentCreateRequest,
    CommentResponse,
    CommentUpdateRequest,
    EmojiReactionRequest,
    EmojiReactionResponse,
    EventAnnouncementPostsRequest,
    EventAnnouncementPostsResponse,
    EventAnnouncementRequest,
    EventAnnouncementResponse,
    EventPostCreateRequest,
    FeedResponse,
    GroupResponse,
    MembershipResponse,
    PostCreateRequest,
    PostResponse,
    PostUpdateRequest,
    ReactionRequest,
    ReportCreateRequest,
    ReportDecisionRequest,
    ReportResponse,
    SafetyAuditLogResponse,
    SimpleStatusResponse,
    SocialCapabilitiesResponse,
)
from social.api.security import (
    CurrentUser,
    require_current_user,
    require_internal_token,
    require_write_quota,
)
from social.domain.models import (
    Comment,
    CommentMention,
    CommentReaction,
    EventAnnouncement,
    Group,
    GroupMembership,
    Post,
    PostEmojiReaction,
    PostMention,
    Reaction,
    SafetyAuditLog,
    SafetyReport,
    UserBlock,
    utc_now,
)
from social.events import publish_event
from social.main_dependencies import get_db_session, settings
from social.mentions import MentionCandidate, extract_mention_candidates
from social.users_client import (
    create_notification,
    list_following_user_ids,
    resolve_event_mention,
    resolve_profile_or_page_mention,
)
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import Select

from social import media_client
from threshold_common.pagination import clamp_limit

router = APIRouter(dependencies=[Depends(require_internal_token)])
DbSession = Annotated[Session, Depends(get_db_session)]
CurrentPrincipal = Annotated[CurrentUser, Depends(require_current_user)]
WriteQuota = Annotated[None, Depends(require_write_quota)]

MAX_DISTINCT_EMOJI_PER_POST = 20
MAX_MENTIONS_PER_ITEM = 10


@router.get("/internal/v1/capabilities", response_model=SocialCapabilitiesResponse)
def get_internal_capabilities() -> SocialCapabilitiesResponse:
    return SocialCapabilitiesResponse()


class ResolvedMention:
    def __init__(
        self,
        *,
        mention_type: str,
        target_handle: str,
        target_id: str | None,
        display_name: str | None,
        target_url: str | None,
        start_index: int | None,
        end_index: int | None,
        recipient_user_id: str | None = None,
    ) -> None:
        self.mention_type = mention_type
        self.target_handle = target_handle
        self.target_id = target_id
        self.display_name = display_name
        self.target_url = target_url
        self.start_index = start_index
        self.end_index = end_index
        self.recipient_user_id = recipient_user_id


def optional_viewer_id(
    user_id: Annotated[str | None, Header(alias="X-Threshold-User-Id")] = None,
) -> str | None:
    """Viewer identity for GETs; set by the BFF from the session, never by clients."""
    return user_id or None


ViewerId = Annotated[str | None, Depends(optional_viewer_id)]


def _normalize_handle(value: str | None) -> str | None:
    if value is None:
        return None
    handle = value.strip().lstrip("@").lower()
    return handle or None


def _block_row(session: Session, blocker_user_id: str, blocked_user_id: str) -> UserBlock | None:
    return session.scalar(
        select(UserBlock).where(
            UserBlock.blocker_user_id == blocker_user_id,
            UserBlock.blocked_user_id == blocked_user_id,
        )
    )


def _is_blocked(session: Session, *, blocker_user_id: str, blocked_user_id: str) -> bool:
    return _block_row(session, blocker_user_id, blocked_user_id) is not None


def _blocked_blocker_handles(session: Session, blocked_user_id: str) -> set[str]:
    return {
        username
        for username in session.scalars(
            select(UserBlock.blocker_username).where(
                UserBlock.blocked_user_id == blocked_user_id,
                UserBlock.blocker_username.is_not(None),
            )
        ).all()
        if username
    }


def _reject_blocked_mentions(session: Session, *, author_user_id: str, mentions: list[Any]) -> None:
    handles = _blocked_blocker_handles(session, author_user_id)
    if not handles:
        return
    for mention in mentions:
        if mention.mention_type == "user" and mention.target_handle in handles:
            raise HTTPException(status_code=403, detail="blocked user cannot mention blocker")


def _reject_blocked_resolved_mentions(
    session: Session, *, author_user_id: str, mentions: list[ResolvedMention]
) -> None:
    for mention in mentions:
        if mention.recipient_user_id and _is_blocked(
            session,
            blocker_user_id=mention.recipient_user_id,
            blocked_user_id=author_user_id,
        ):
            raise HTTPException(status_code=403, detail="blocked user cannot mention blocker")


def _visible_post(session: Session, post_id: str) -> Post:
    post = session.get(Post, post_id)
    if post is None or post.hidden_at is not None:
        raise HTTPException(status_code=404, detail="post not found")
    return post


def _visible_comment(session: Session, comment_id: str) -> Comment:
    comment = session.get(Comment, comment_id)
    if comment is None or comment.hidden_at is not None or comment.post.hidden_at is not None:
        raise HTTPException(status_code=404, detail="comment not found")
    return comment


def _blocked_feed_author_ids(session: Session, viewer_id: str) -> set[str]:
    rows = session.execute(
        select(UserBlock.blocker_user_id, UserBlock.blocked_user_id).where(
            or_(UserBlock.blocker_user_id == viewer_id, UserBlock.blocked_user_id == viewer_id)
        )
    ).all()
    blocked: set[str] = set()
    for blocker_id, blocked_id in rows:
        blocked.add(blocked_id if blocker_id == viewer_id else blocker_id)
    return blocked


def _validate_post_media_assets(asset_ids: list[str], owner_user_id: str) -> None:
    for asset_id in asset_ids:
        try:
            media_client.validate_post_image_asset(
                settings, asset_id=asset_id, owner_user_id=owner_user_id
            )
        except media_client.MediaAssetValidationError as exc:
            raise HTTPException(status_code=422, detail="invalid post media asset") from exc


def _candidate_key(candidate: MentionCandidate) -> tuple[str, str, int | None, int | None]:
    return (candidate.kind, candidate.handle, candidate.start_index, candidate.end_index)


def _explicit_candidate(mention: Any) -> MentionCandidate:
    kind = "profile" if mention.mention_type in {"user", "artist", "page"} else mention.mention_type
    return MentionCandidate(
        kind=kind,
        handle=mention.target_handle,
        start_index=-1,
        end_index=-1,
    )


async def _resolve_mentions(body: str, explicit_mentions: list[Any]) -> list[ResolvedMention]:
    candidates = extract_mention_candidates(body)
    seen = {_candidate_key(candidate) for candidate in candidates}
    for mention in explicit_mentions:
        candidate = _explicit_candidate(mention)
        key = _candidate_key(candidate)
        if key not in seen:
            candidates.append(candidate)
            seen.add(key)
    if len(candidates) > MAX_MENTIONS_PER_ITEM:
        raise HTTPException(status_code=422, detail="too many mentions")

    resolved: list[ResolvedMention] = []
    target_seen: set[tuple[str, str | None]] = set()
    for candidate in candidates:
        payload = None
        if candidate.kind == "event":
            payload = await resolve_event_mention(settings, candidate.handle)
        else:
            payload = await resolve_profile_or_page_mention(settings, candidate.handle)
        if payload is None:
            raise HTTPException(status_code=422, detail="mention target not found")
        target_type = str(payload.get("target_type") or candidate.kind)
        target_id = payload.get("target_id")
        target_key = (target_type, str(target_id) if target_id is not None else None)
        if target_key in target_seen:
            continue
        target_seen.add(target_key)
        resolved.append(
            ResolvedMention(
                mention_type=target_type,
                target_handle=str(payload.get("handle") or candidate.handle),
                target_id=str(target_id) if target_id is not None else None,
                display_name=str(payload.get("display_name"))
                if payload.get("display_name") is not None
                else None,
                target_url=str(payload.get("target_url"))
                if payload.get("target_url") is not None
                else None,
                start_index=None if candidate.start_index < 0 else candidate.start_index,
                end_index=None if candidate.end_index < 0 else candidate.end_index,
                recipient_user_id=str(payload.get("recipient_user_id"))
                if payload.get("recipient_user_id") is not None
                else None,
            )
        )
    return resolved


async def _notify_mentions(
    mentions: list[ResolvedMention], *, actor: CurrentUser, target_type: str, target_id: str
) -> None:
    for mention in mentions:
        if mention.recipient_user_id is None:
            continue
        await create_notification(
            settings,
            recipient_user_id=mention.recipient_user_id,
            actor_user_id=actor.user_id,
            event_type="mention.created",
            target_type=target_type,
            target_id=target_id,
            target_url=f"/{target_type}s/{target_id}",
            title=f"{actor.display_name} mentioned you",
            dedupe_key=f"mention:{target_type}:{target_id}:{mention.recipient_user_id}",
            metadata={
                "mention_type": mention.mention_type,
                "handle": mention.target_handle,
                "actor_username": actor.username,
                "actor_display_name": actor.display_name,
            },
        )


SENSITIVE_AUDIT_KEYS = ("email", "token", "password", "secret", "exact_address")


def _safe_audit_metadata(
    metadata: dict[str, str | int | bool | None],
) -> dict[str, str | int | bool | None]:
    return {
        key: value
        for key, value in metadata.items()
        if not any(marker in key.lower() for marker in SENSITIVE_AUDIT_KEYS)
        and not any(marker in str(value).lower() for marker in SENSITIVE_AUDIT_KEYS)
    }


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


def _ensure_report_target_exists(session: Session, payload: ReportCreateRequest) -> None:
    if payload.target_type == "post":
        post = session.get(Post, payload.target_id)
        missing = post is None or post.hidden_at is not None
    elif payload.target_type == "comment":
        comment = session.get(Comment, payload.target_id)
        missing = comment is None or comment.hidden_at is not None
    else:
        missing = False
    if missing:
        raise HTTPException(status_code=404, detail="report target not found")


def _apply_moderation_action(session: Session, report: SafetyReport, action: str) -> None:
    if report.target_type == "post":
        post = session.get(Post, report.target_id)
        if post is None:
            return
        if action == "delete" and post.author_type == "system":
            raise HTTPException(status_code=403, detail="system posts cannot be deleted")
        if action == "hide":
            post.hidden_at = utc_now()
        elif action == "delete":
            session.delete(post)
    elif report.target_type == "comment":
        comment = session.get(Comment, report.target_id)
        if comment is None:
            return
        if action == "hide":
            comment.hidden_at = utc_now()
        elif action == "delete":
            session.delete(comment)


def _clamp_limit(limit: int | None) -> int:
    return clamp_limit(limit, default=settings.default_feed_limit, maximum=settings.max_feed_limit)


def _encode_cursor(post: Post | Comment | None) -> str | None:
    if post is None:
        return None
    return f"{post.created_at.isoformat()}|{post.id}"


def _cursor_condition(
    model: type[Post] | type[Comment], before: str | None
) -> ColumnElement[bool] | None:
    if not before:
        return None
    try:
        raw_created_at, raw_id = before.split("|", 1)
        created_at = datetime.fromisoformat(raw_created_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid cursor") from exc
    return or_(
        model.created_at < created_at,
        and_(model.created_at == created_at, model.id < raw_id),
    )


def _post_reaction_counts(
    session: Session, post_ids: list[str]
) -> tuple[dict[str, int], dict[str, int]]:
    up_counts: dict[str, int] = defaultdict(int)
    down_counts: dict[str, int] = defaultdict(int)
    for post_id, kind, count in session.execute(
        select(Reaction.post_id, Reaction.kind, func.count(Reaction.id))
        .where(Reaction.post_id.in_(post_ids))
        .group_by(Reaction.post_id, Reaction.kind)
    ).all():
        if kind == "down":
            down_counts[post_id] = count
        else:
            up_counts[post_id] = count
    return up_counts, down_counts


def _post_comment_counts(session: Session, post_ids: list[str]) -> dict[str, int]:
    return dict(
        session.execute(
            select(Comment.post_id, func.count(Comment.id))
            .where(Comment.post_id.in_(post_ids), Comment.hidden_at.is_(None))
            .group_by(Comment.post_id)
        ).all()  # type: ignore[arg-type]
    )


def _post_mentions(session: Session, post_ids: list[str]) -> dict[str, list[PostMention]]:
    mentions: dict[str, list[PostMention]] = defaultdict(list)
    for mention in session.scalars(
        select(PostMention)
        .where(PostMention.post_id.in_(post_ids))
        .order_by(PostMention.created_at, PostMention.id)
    ).all():
        mentions[mention.post_id].append(mention)
    return mentions


def _legacy_event_refs(
    session: Session, posts: list[Post]
) -> dict[str, tuple[str | None, str | None]]:
    post_ids = [
        post.id for post in posts if post.event_id is None or post.event_slug is None
    ]
    if not post_ids:
        return {}
    ranked = (
        select(
            EventAnnouncement.post_id,
            EventAnnouncement.event_id,
            EventAnnouncement.event_slug,
            func.row_number()
            .over(
                partition_by=EventAnnouncement.post_id,
                order_by=(EventAnnouncement.created_at, EventAnnouncement.id),
            )
            .label("row_number"),
        )
        .where(EventAnnouncement.post_id.in_(post_ids))
        .subquery()
    )
    return {
        post_id: (event_id, event_slug)
        for post_id, event_id, event_slug in session.execute(
            select(ranked.c.post_id, ranked.c.event_id, ranked.c.event_slug).where(
                ranked.c.row_number == 1
            )
        ).all()
    }


def _viewer_post_state(
    session: Session, post_ids: list[str], viewer_id: str | None
) -> tuple[dict[str, str], set[tuple[str, str]]]:
    if not viewer_id:
        return {}, set()
    viewer_votes: dict[str, str] = dict(
        session.execute(
            select(Reaction.post_id, Reaction.kind).where(
                Reaction.post_id.in_(post_ids), Reaction.user_id == viewer_id
            )
        ).all()  # type: ignore[arg-type]
    )
    viewer_emojis = {
        (post_id, emoji)
        for post_id, emoji in session.execute(
            select(PostEmojiReaction.post_id, PostEmojiReaction.emoji).where(
                PostEmojiReaction.post_id.in_(post_ids),
                PostEmojiReaction.user_id == viewer_id,
            )
        ).all()
    }
    return viewer_votes, viewer_emojis


def _post_emoji_summary(
    session: Session, post_ids: list[str], viewer_emojis: set[tuple[str, str]]
) -> dict[str, list[EmojiReactionResponse]]:
    emoji_rows = session.execute(
        select(
            PostEmojiReaction.post_id,
            PostEmojiReaction.emoji,
            func.count(PostEmojiReaction.id),
            func.min(PostEmojiReaction.created_at),
        )
        .where(PostEmojiReaction.post_id.in_(post_ids))
        .group_by(PostEmojiReaction.post_id, PostEmojiReaction.emoji)
    ).all()

    emoji_by_post: dict[str, list[EmojiReactionResponse]] = defaultdict(list)
    for post_id, emoji, count, _first_at in sorted(emoji_rows, key=lambda row: row[3]):
        emoji_by_post[post_id].append(
            EmojiReactionResponse(
                emoji=emoji,
                count=count,
                viewer_reacted=(post_id, emoji) in viewer_emojis,
            )
        )
    return emoji_by_post


def _posts_response(
    session: Session, posts: list[Post], viewer_id: str | None
) -> list[PostResponse]:
    """Build post responses with batched aggregates (no per-post N+1)."""
    if not posts:
        return []
    post_ids = [post.id for post in posts]
    up_counts, down_counts = _post_reaction_counts(session, post_ids)
    comment_counts = _post_comment_counts(session, post_ids)
    mentions_by_post = _post_mentions(session, post_ids)
    legacy_event_refs = _legacy_event_refs(session, posts)
    viewer_votes, viewer_emojis = _viewer_post_state(session, post_ids, viewer_id)
    emoji_by_post = _post_emoji_summary(session, post_ids, viewer_emojis)

    responses: list[PostResponse] = []
    for post in posts:
        up_count = up_counts.get(post.id, 0)
        legacy_event_id, legacy_event_slug = legacy_event_refs.get(
            post.id, (None, None)
        )
        responses.append(
            PostResponse.model_validate(
                {
                    **post.__dict__,
                    "event_id": post.event_id or legacy_event_id,
                    "event_slug": post.event_slug or legacy_event_slug,
                    "up_count": up_count,
                    "down_count": down_counts.get(post.id, 0),
                    "viewer_vote": viewer_votes.get(post.id),
                    "viewer_is_author": (
                        viewer_id is not None
                        and post.author_type != "system"
                        and post.author_user_id == viewer_id
                    ),
                    "emoji_reactions": emoji_by_post.get(post.id, []),
                    "like_count": up_count,
                    "comment_count": comment_counts.get(post.id, 0),
                    "mentions": mentions_by_post.get(post.id, []),
                }
            )
        )
    return responses


def _post_response(session: Session, post: Post, viewer_id: str | None) -> PostResponse:
    return _posts_response(session, [post], viewer_id)[0]


def _comments_response(
    session: Session, comments: list[Comment], viewer_id: str | None
) -> list[CommentResponse]:
    """Build comment responses with batched vote aggregates."""
    if not comments:
        return []
    comment_ids = [comment.id for comment in comments]

    up_counts: dict[str, int] = defaultdict(int)
    down_counts: dict[str, int] = defaultdict(int)
    for comment_id, kind, count in session.execute(
        select(CommentReaction.comment_id, CommentReaction.kind, func.count(CommentReaction.id))
        .where(CommentReaction.comment_id.in_(comment_ids))
        .group_by(CommentReaction.comment_id, CommentReaction.kind)
    ).all():
        if kind == "down":
            down_counts[comment_id] = count
        else:
            up_counts[comment_id] = count

    viewer_votes: dict[str, str] = {}
    if viewer_id:
        viewer_votes = dict(
            session.execute(
                select(CommentReaction.comment_id, CommentReaction.kind).where(
                    CommentReaction.comment_id.in_(comment_ids),
                    CommentReaction.user_id == viewer_id,
                )
            ).all()  # type: ignore[arg-type]
        )

    return [
        CommentResponse.model_validate(
            {
                **comment.__dict__,
                "up_count": up_counts.get(comment.id, 0),
                "down_count": down_counts.get(comment.id, 0),
                "viewer_vote": viewer_votes.get(comment.id),
                "viewer_is_author": viewer_id is not None and comment.author_user_id == viewer_id,
                "mentions": comment.mentions,
            }
        )
        for comment in comments
    ]


def _paginate_posts(
    statement: Select[tuple[Post]], session: Session, limit: int, viewer_id: str | None
) -> FeedResponse:
    rows = session.scalars(
        statement.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit + 1)
    ).all()
    visible = list(rows[:limit])
    next_before = _encode_cursor(visible[-1]) if len(rows) > limit and visible else None
    return FeedResponse(items=_posts_response(session, visible, viewer_id), next_before=next_before)


@router.get("/v1/groups", response_model=list[GroupResponse])
def list_groups(session: DbSession) -> list[GroupResponse]:
    groups = session.scalars(select(Group).order_by(Group.official.desc(), Group.name)).all()
    return [GroupResponse.model_validate(group) for group in groups]


@router.get("/v1/groups/{slug}", response_model=GroupResponse)
def get_group(slug: str, session: DbSession) -> GroupResponse:
    group = session.scalar(select(Group).where(Group.slug == slug))
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    return GroupResponse.model_validate(group)


@router.post("/v1/groups/{slug}/membership", response_model=MembershipResponse)
def join_group(
    slug: str, user: CurrentPrincipal, _: WriteQuota, session: DbSession
) -> MembershipResponse:
    group = session.scalar(select(Group).where(Group.slug == slug))
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    existing = session.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group.id,
            GroupMembership.user_id == user.user_id,
        )
    )
    if existing is None:
        session.add(GroupMembership(group_id=group.id, user_id=user.user_id))
        session.commit()
    return MembershipResponse(status="ok")


@router.delete("/v1/groups/{slug}/membership", status_code=status.HTTP_204_NO_CONTENT)
def leave_group(
    slug: str, user: CurrentPrincipal, _: WriteQuota, session: DbSession, response: Response
) -> Response:
    group = session.scalar(select(Group).where(Group.slug == slug))
    if group is not None:
        membership = session.scalar(
            select(GroupMembership).where(
                GroupMembership.group_id == group.id,
                GroupMembership.user_id == user.user_id,
            )
        )
        if membership is not None:
            session.delete(membership)
            session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/v1/me/groups", response_model=list[GroupResponse])
def list_my_groups(user: CurrentPrincipal, session: DbSession) -> list[GroupResponse]:
    groups = session.scalars(
        select(Group)
        .join(GroupMembership)
        .where(GroupMembership.user_id == user.user_id)
        .order_by(Group.name)
    ).all()
    return [GroupResponse.model_validate(group) for group in groups]


@router.post("/internal/v1/event-announcements", response_model=EventAnnouncementResponse)
def create_event_announcement(
    payload: EventAnnouncementRequest,
    session: DbSession,
    http_response: Response,
) -> EventAnnouncementResponse:
    existing = session.scalar(
        select(EventAnnouncement).where(EventAnnouncement.event_id == payload.event_id)
    )
    if existing is not None:
        http_response.status_code = status.HTTP_200_OK
        return EventAnnouncementResponse(
            event_id=existing.event_id,
            event_slug=existing.event_slug,
            post_id=existing.post_id,
            group_id=existing.group_id,
            created_at=existing.created_at,
        )

    group = session.scalar(
        select(Group)
        .where(Group.city == payload.city, Group.official.is_(True))
        .order_by(Group.name)
    )
    if group is None:
        raise HTTPException(status_code=404, detail="official city group not found")

    post = Post(
        author_user_id=payload.actor_user_id,
        author_username="threshold-events",
        author_display_name="Threshold Events",
        author_type="system",
        group_id=group.id,
        event_id=payload.event_id,
        event_slug=payload.event_slug,
        body=f"New event: {payload.event_title}\n/events/{payload.event_slug}",
    )
    session.add(post)
    session.flush()
    announcement = EventAnnouncement(
        event_id=payload.event_id,
        event_slug=payload.event_slug,
        post_id=post.id,
        group_id=group.id,
    )
    session.add(announcement)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(EventAnnouncement).where(EventAnnouncement.event_id == payload.event_id)
        )
        if existing is None:
            raise
        http_response.status_code = status.HTTP_200_OK
        return EventAnnouncementResponse(
            event_id=existing.event_id,
            event_slug=existing.event_slug,
            post_id=existing.post_id,
            group_id=existing.group_id,
            created_at=existing.created_at,
        )
    session.refresh(announcement)
    http_response.status_code = status.HTTP_201_CREATED
    return EventAnnouncementResponse(
        event_id=announcement.event_id,
        event_slug=announcement.event_slug,
        post_id=announcement.post_id,
        group_id=announcement.group_id,
        created_at=announcement.created_at,
    )


@router.post(
    "/internal/v1/event-announcements/batch",
    response_model=EventAnnouncementPostsResponse,
)
def get_event_announcement_posts(
    payload: EventAnnouncementPostsRequest,
    session: DbSession,
    user: CurrentPrincipal,
) -> EventAnnouncementPostsResponse:
    viewer_id = user.user_id
    event_ids = list(dict.fromkeys(payload.event_ids))
    event_slugs = list(dict.fromkeys(payload.event_slugs))
    if not event_ids and not event_slugs:
        return EventAnnouncementPostsResponse(
            posts=[],
            represented_event_ids=[],
            represented_event_slugs=[],
        )

    id_rows = (
        session.execute(
            select(EventAnnouncement, Post)
            .join(Post, Post.id == EventAnnouncement.post_id)
            .where(
                EventAnnouncement.event_id.in_(event_ids),
            )
        )
        .tuples()
        .all()
        if event_ids
        else []
    )
    id_matches = {announcement.event_id: (announcement, post) for announcement, post in id_rows}

    slug_rows: list[tuple[EventAnnouncement, Post]] = []
    if event_slugs:
        ranked_slugs = (
            select(
                EventAnnouncement.id.label("announcement_id"),
                func.row_number()
                .over(
                    partition_by=EventAnnouncement.event_slug,
                    order_by=(EventAnnouncement.created_at, EventAnnouncement.id),
                )
                .label("row_number"),
            )
            .select_from(EventAnnouncement)
            .join(Post, Post.id == EventAnnouncement.post_id)
            .where(
                EventAnnouncement.event_slug.in_(event_slugs),
            )
            .subquery()
        )
        slug_rows = list(
            session.execute(
                select(EventAnnouncement, Post)
                .select_from(EventAnnouncement)
                .join(
                    ranked_slugs,
                    ranked_slugs.c.announcement_id == EventAnnouncement.id,
                )
                .join(Post, Post.id == EventAnnouncement.post_id)
                .where(ranked_slugs.c.row_number == 1)
            )
            .tuples()
            .all()
        )
    slug_matches = {
        announcement.event_slug: (announcement, post)
        for announcement, post in slug_rows
    }

    selected = [
        id_matches[event_id] for event_id in event_ids if event_id in id_matches
    ] + [
        slug_matches[event_slug]
        for event_slug in event_slugs
        if event_slug in slug_matches
    ]
    selected_by_announcement = {
        announcement.id: (announcement, post) for announcement, post in selected
    }
    ordered = sorted(
        selected_by_announcement.values(),
        key=lambda item: (item[1].created_at, item[1].id, item[0].id),
        reverse=True,
    )
    posts: list[Post] = []
    seen_post_ids: set[str] = set()
    for _, post in ordered:
        if (
            post.id in seen_post_ids
            or post.author_type != "system"
            or post.hidden_at is not None
        ):
            continue
        seen_post_ids.add(post.id)
        posts.append(post)
    blocked_author_ids = _blocked_feed_author_ids(session, viewer_id)
    posts = [
        post for post in posts if post.author_user_id not in blocked_author_ids
    ]
    return EventAnnouncementPostsResponse(
        posts=_posts_response(session, posts, viewer_id),
        represented_event_ids=[
            event_id for event_id in event_ids if event_id in id_matches
        ],
        represented_event_slugs=[
            event_slug for event_slug in event_slugs if event_slug in slug_matches
        ],
    )


async def _create_post(
    payload: PostCreateRequest,
    user: CurrentUser,
    session: Session,
) -> PostResponse:
    group_id: str | None = None
    if payload.group_slug:
        group = session.scalar(select(Group).where(Group.slug == payload.group_slug))
        if group is None:
            raise HTTPException(status_code=404, detail="group not found")
        membership = session.scalar(
            select(GroupMembership.id).where(
                GroupMembership.group_id == group.id,
                GroupMembership.user_id == user.user_id,
            )
        )
        if membership is None:
            raise HTTPException(status_code=403, detail="group membership required")
        group_id = group.id
    _reject_blocked_mentions(session, author_user_id=user.user_id, mentions=payload.mentions)
    resolved_mentions = await _resolve_mentions(payload.body, payload.mentions)
    for mention in resolved_mentions:
        if mention.recipient_user_id and _is_blocked(
            session, blocker_user_id=mention.recipient_user_id, blocked_user_id=user.user_id
        ):
            raise HTTPException(status_code=403, detail="blocked user cannot mention blocker")
    _validate_post_media_assets(payload.media_asset_ids, user.user_id)
    post = Post(
        author_user_id=user.user_id,
        author_username=user.username,
        author_display_name=user.display_name,
        author_type="user",
        group_id=group_id,
        event_id=payload.event_id,
        event_slug=payload.event_slug,
        body=payload.body,
        media_asset_ids=payload.media_asset_ids,
    )
    session.add(post)
    for mention in resolved_mentions:
        post.mentions.append(
            PostMention(
                mention_type=mention.mention_type,
                target_handle=mention.target_handle,
                target_id=mention.target_id,
                display_name=mention.display_name,
                target_url=mention.target_url,
                start_index=mention.start_index,
                end_index=mention.end_index,
            )
        )
    session.commit()
    session.refresh(post)
    await _notify_mentions(resolved_mentions, actor=user, target_type="post", target_id=post.id)
    await publish_event(
        settings,
        settings.post_created_subject,
        {
            "post_id": post.id,
            "author_user_id": post.author_user_id,
            "group_id": post.group_id,
            "created_at": post.created_at.isoformat(),
        },
    )
    return _post_response(session, post, user.user_id)


@router.post("/v1/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: PostCreateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> PostResponse:
    return await _create_post(payload, user, session)


@router.post(
    "/v1/event-posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_event_post(
    payload: EventPostCreateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> PostResponse:
    return await _create_post(payload, user, session)


@router.get("/v1/groups/{slug}/posts", response_model=FeedResponse)
def list_group_posts(
    slug: str,
    session: DbSession,
    viewer_id: ViewerId = None,
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> FeedResponse:
    group = session.scalar(select(Group).where(Group.slug == slug))
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    conditions = [Post.group_id == group.id]
    cursor_condition = _cursor_condition(Post, before)
    if cursor_condition is not None:
        conditions.append(cursor_condition)
    statement = select(Post).where(*conditions, Post.hidden_at.is_(None))
    return _paginate_posts(statement, session, _clamp_limit(limit), viewer_id)


@router.get("/v1/posts/{post_id}", response_model=PostResponse)
def get_post(post_id: str, session: DbSession, viewer_id: ViewerId = None) -> PostResponse:
    post = _visible_post(session, post_id)
    return _post_response(session, post, viewer_id)


@router.patch("/v1/posts/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: str,
    payload: PostUpdateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> PostResponse:
    post = _visible_post(session, post_id)
    if post.author_type == "system":
        raise HTTPException(status_code=403, detail="system posts cannot be edited")
    if post.author_user_id != user.user_id:
        raise HTTPException(status_code=403, detail="only the author can edit this post")
    resolved_mentions = await _resolve_mentions(payload.body, [])
    _reject_blocked_resolved_mentions(
        session, author_user_id=user.user_id, mentions=resolved_mentions
    )
    post.body = payload.body
    post.edited_at = utc_now()
    session.execute(delete(PostMention).where(PostMention.post_id == post.id))
    for mention in resolved_mentions:
        post.mentions.append(
            PostMention(
                mention_type=mention.mention_type,
                target_handle=mention.target_handle,
                target_id=mention.target_id,
                display_name=mention.display_name,
                target_url=mention.target_url,
                start_index=mention.start_index,
                end_index=mention.end_index,
            )
        )
    session.commit()
    session.refresh(post)
    return _post_response(session, post, user.user_id)


@router.delete("/v1/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: str,
    user: CurrentPrincipal,
    session: DbSession,
) -> Response:
    post = session.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    if post.author_type == "system":
        raise HTTPException(status_code=403, detail="system posts cannot be deleted")
    if post.author_user_id != user.user_id:
        raise HTTPException(status_code=403, detail="only the author can delete this post")
    # Bulk SQL deletes (children first) instead of ORM cascades: comments are
    # removed in one statement, and DB-level FK cascades clear their votes.
    session.execute(delete(Comment).where(Comment.post_id == post_id))
    session.execute(delete(Reaction).where(Reaction.post_id == post_id))
    session.execute(delete(PostEmojiReaction).where(PostEmojiReaction.post_id == post_id))
    session.execute(delete(PostMention).where(PostMention.post_id == post_id))
    session.execute(delete(Post).where(Post.id == post_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/v1/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: str,
    payload: CommentUpdateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> CommentResponse:
    comment = _visible_comment(session, comment_id)
    if comment.author_user_id != user.user_id:
        raise HTTPException(status_code=403, detail="only the author can edit this comment")
    resolved_mentions = await _resolve_mentions(payload.body, [])
    _reject_blocked_resolved_mentions(
        session, author_user_id=user.user_id, mentions=resolved_mentions
    )
    comment.body = payload.body
    comment.edited_at = utc_now()
    session.execute(delete(CommentMention).where(CommentMention.comment_id == comment.id))
    for mention in resolved_mentions:
        comment.mentions.append(
            CommentMention(
                mention_type=mention.mention_type,
                target_handle=mention.target_handle,
                target_id=mention.target_id,
                display_name=mention.display_name,
                target_url=mention.target_url,
                start_index=mention.start_index,
                end_index=mention.end_index,
            )
        )
    session.commit()
    session.refresh(comment)
    return _comments_response(session, [comment], user.user_id)[0]


@router.delete("/v1/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: str,
    user: CurrentPrincipal,
    session: DbSession,
) -> Response:
    comment = session.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")
    if comment.author_user_id != user.user_id:
        raise HTTPException(status_code=403, detail="only the author can delete this comment")
    # FK ON DELETE CASCADE removes replies and their votes with the comment.
    session.execute(delete(Comment).where(Comment.id == comment_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _validate_comment_parent(
    session: Session, *, post: Post, parent_id: str | None
) -> Comment | None:
    if parent_id is None:
        return None
    parent = session.get(Comment, parent_id)
    if parent is None or parent.post_id != post.id:
        raise HTTPException(status_code=400, detail="parent comment not found")
    if parent.parent_id is not None:
        grandparent = session.get(Comment, parent.parent_id)
        if grandparent is not None and grandparent.parent_id is not None:
            raise HTTPException(status_code=400, detail="replies are limited to two levels")
    return parent


def _build_comment(post: Post, payload: CommentCreateRequest, user: CurrentUser) -> Comment:
    return Comment(
        post_id=post.id,
        parent_id=payload.parent_id,
        author_user_id=user.user_id,
        author_username=user.username,
        author_display_name=user.display_name,
        author_type="user",
        body=payload.body,
    )


def _attach_comment_mentions(comment: Comment, mentions: list[ResolvedMention]) -> None:
    for mention in mentions:
        comment.mentions.append(
            CommentMention(
                mention_type=mention.mention_type,
                target_handle=mention.target_handle,
                target_id=mention.target_id,
                display_name=mention.display_name,
                target_url=mention.target_url,
                start_index=mention.start_index,
                end_index=mention.end_index,
            )
        )


async def _notify_comment_created(
    *, post: Post, comment: Comment, actor: CurrentUser, mentions: list[ResolvedMention]
) -> None:
    await publish_event(
        settings,
        settings.comment_created_subject,
        {
            "comment_id": comment.id,
            "post_id": comment.post_id,
            "parent_id": comment.parent_id,
            "author_user_id": comment.author_user_id,
            "created_at": comment.created_at.isoformat(),
        },
    )
    await create_notification(
        settings,
        recipient_user_id=post.author_user_id,
        actor_user_id=actor.user_id,
        event_type="comment.created",
        target_type="post",
        target_id=post.id,
        target_url=f"/posts/{post.id}",
        title=f"{actor.username or actor.display_name or 'Someone'} commented on your post",
        dedupe_key=f"comment:{post.id}:{actor.user_id}:{post.author_user_id}",
        metadata={
            "post_id": post.id,
            "comment_id": comment.id,
            "actor_username": actor.username,
            "actor_display_name": actor.display_name,
        },
    )
    await _notify_mentions(mentions, actor=actor, target_type="comment", target_id=comment.id)


@router.post("/v1/posts/{post_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    post_id: str,
    payload: CommentCreateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> CommentResponse:
    post = _visible_post(session, post_id)
    if _is_blocked(session, blocker_user_id=post.author_user_id, blocked_user_id=user.user_id):
        raise HTTPException(
            status_code=403,
            detail="blocked user cannot comment on blocker content",
        )
    _validate_comment_parent(session, post=post, parent_id=payload.parent_id)
    _reject_blocked_mentions(session, author_user_id=user.user_id, mentions=payload.mentions)
    resolved_mentions = await _resolve_mentions(payload.body, payload.mentions)
    _reject_blocked_resolved_mentions(
        session, author_user_id=user.user_id, mentions=resolved_mentions
    )
    comment = _build_comment(post, payload, user)
    session.add(comment)
    _attach_comment_mentions(comment, resolved_mentions)
    session.commit()
    session.refresh(comment)
    await _notify_comment_created(
        post=post,
        comment=comment,
        actor=user,
        mentions=resolved_mentions,
    )
    # Through the response builder so the creator gets viewer_is_author=True.
    return _comments_response(session, [comment], user.user_id)[0]


@router.get("/v1/posts/{post_id}/comments", response_model=list[CommentResponse])
def list_comments(
    post_id: str,
    session: DbSession,
    viewer_id: ViewerId = None,
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> list[CommentResponse]:
    _visible_post(session, post_id)
    conditions = [Comment.post_id == post_id, Comment.hidden_at.is_(None)]
    cursor_condition = _cursor_condition(Comment, before)
    if cursor_condition is not None:
        conditions.append(cursor_condition)
    rows = session.scalars(
        select(Comment)
        .where(*conditions)
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .limit(_clamp_limit(limit))
    ).all()
    return _comments_response(session, list(rows), viewer_id)


@router.put("/v1/posts/{post_id}/reaction", response_model=SimpleStatusResponse)
def vote_post(
    post_id: str,
    payload: ReactionRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> SimpleStatusResponse:
    _visible_post(session, post_id)
    reaction = session.scalar(
        select(Reaction).where(Reaction.post_id == post_id, Reaction.user_id == user.user_id)
    )
    if reaction is None:
        session.add(Reaction(post_id=post_id, user_id=user.user_id, kind=payload.kind))
        try:
            session.commit()
        except IntegrityError:
            # Concurrent insert won the unique race: update the existing row instead.
            session.rollback()
            reaction = session.scalar(
                select(Reaction).where(
                    Reaction.post_id == post_id, Reaction.user_id == user.user_id
                )
            )
            if reaction is not None:
                reaction.kind = payload.kind
                session.commit()
    else:
        reaction.kind = payload.kind
        session.commit()
    return SimpleStatusResponse(status="ok")


@router.delete("/v1/posts/{post_id}/reaction", status_code=status.HTTP_204_NO_CONTENT)
def remove_post_vote(
    post_id: str, user: CurrentPrincipal, _: WriteQuota, session: DbSession, response: Response
) -> Response:
    _visible_post(session, post_id)
    reaction = session.scalar(
        select(Reaction).where(Reaction.post_id == post_id, Reaction.user_id == user.user_id)
    )
    if reaction is not None:
        session.delete(reaction)
        session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.put("/v1/comments/{comment_id}/reaction", response_model=SimpleStatusResponse)
def vote_comment(
    comment_id: str,
    payload: ReactionRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> SimpleStatusResponse:
    _visible_comment(session, comment_id)
    reaction = session.scalar(
        select(CommentReaction).where(
            CommentReaction.comment_id == comment_id,
            CommentReaction.user_id == user.user_id,
        )
    )
    if reaction is None:
        session.add(CommentReaction(comment_id=comment_id, user_id=user.user_id, kind=payload.kind))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            reaction = session.scalar(
                select(CommentReaction).where(
                    CommentReaction.comment_id == comment_id,
                    CommentReaction.user_id == user.user_id,
                )
            )
            if reaction is not None:
                reaction.kind = payload.kind
                session.commit()
    else:
        reaction.kind = payload.kind
        session.commit()
    return SimpleStatusResponse(status="ok")


@router.delete("/v1/comments/{comment_id}/reaction", status_code=status.HTTP_204_NO_CONTENT)
def remove_comment_vote(
    comment_id: str,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
    response: Response,
) -> Response:
    _visible_comment(session, comment_id)
    reaction = session.scalar(
        select(CommentReaction).where(
            CommentReaction.comment_id == comment_id,
            CommentReaction.user_id == user.user_id,
        )
    )
    if reaction is not None:
        session.delete(reaction)
        session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.put("/v1/posts/{post_id}/emoji", response_model=SimpleStatusResponse)
def add_emoji_reaction(
    post_id: str,
    payload: EmojiReactionRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> SimpleStatusResponse:
    _visible_post(session, post_id)
    existing = session.scalar(
        select(PostEmojiReaction).where(
            PostEmojiReaction.post_id == post_id,
            PostEmojiReaction.user_id == user.user_id,
            PostEmojiReaction.emoji == payload.emoji,
        )
    )
    if existing is not None:
        return SimpleStatusResponse(status="ok")
    distinct_emojis = set(
        session.scalars(
            select(PostEmojiReaction.emoji).where(PostEmojiReaction.post_id == post_id).distinct()
        ).all()
    )
    if payload.emoji not in distinct_emojis and len(distinct_emojis) >= MAX_DISTINCT_EMOJI_PER_POST:
        raise HTTPException(status_code=409, detail="emoji reaction limit reached")
    session.add(PostEmojiReaction(post_id=post_id, user_id=user.user_id, emoji=payload.emoji))
    try:
        session.commit()
    except IntegrityError:
        # Duplicate insert race: the reaction already exists, which is the desired state.
        session.rollback()
    return SimpleStatusResponse(status="ok")


@router.delete("/v1/posts/{post_id}/emoji", status_code=status.HTTP_204_NO_CONTENT)
def remove_emoji_reaction(
    post_id: str,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
    response: Response,
    emoji: Annotated[str, Query(min_length=1, max_length=32)],
) -> Response:
    _visible_post(session, post_id)
    reaction = session.scalar(
        select(PostEmojiReaction).where(
            PostEmojiReaction.post_id == post_id,
            PostEmojiReaction.user_id == user.user_id,
            PostEmojiReaction.emoji == emoji,
        )
    )
    if reaction is not None:
        session.delete(reaction)
        session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/v1/blocks/{blocked_user_id}", response_model=BlockResponse)
def block_user(
    blocked_user_id: str,
    payload: BlockCreateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> BlockResponse:
    if blocked_user_id == user.user_id:
        raise HTTPException(status_code=422, detail="cannot block yourself")
    block = _block_row(session, user.user_id, blocked_user_id)
    if block is None:
        block = UserBlock(
            blocker_user_id=user.user_id,
            blocker_username=_normalize_handle(user.username),
            blocked_user_id=blocked_user_id,
            blocked_username=payload.blocked_username,
        )
        session.add(block)
        _write_safety_audit(
            session,
            actor_user_id=user.user_id,
            action="user.blocked",
            target_type="user",
            target_id=blocked_user_id,
            reason="block",
            metadata={"blocked_username": payload.blocked_username},
        )
    else:
        block.blocker_username = _normalize_handle(user.username)
        block.blocked_username = payload.blocked_username or block.blocked_username
    session.commit()
    session.refresh(block)
    return BlockResponse.model_validate(block)


@router.delete("/v1/blocks/{blocked_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(
    blocked_user_id: str,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
    response: Response,
) -> Response:
    block = _block_row(session, user.user_id, blocked_user_id)
    if block is not None:
        session.delete(block)
        session.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/v1/blocks", response_model=list[BlockResponse])
def list_blocks(user: CurrentPrincipal, session: DbSession) -> list[BlockResponse]:
    rows = session.scalars(
        select(UserBlock)
        .where(UserBlock.blocker_user_id == user.user_id)
        .order_by(UserBlock.created_at.desc())
    ).all()
    return [BlockResponse.model_validate(row) for row in rows]


@router.post("/v1/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreateRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> ReportResponse:
    _ensure_report_target_exists(session, payload)
    report = SafetyReport(
        reporter_user_id=user.user_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
        note=payload.note,
    )
    session.add(report)
    _write_safety_audit(
        session,
        actor_user_id=user.user_id,
        action="report.created",
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
        metadata={},
    )
    session.commit()
    session.refresh(report)
    return ReportResponse.model_validate(report)


@router.get("/v1/moderation/reports", response_model=list[ReportResponse])
def list_reports(
    user: CurrentPrincipal,
    session: DbSession,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[ReportResponse]:
    owned_post_ids = session.scalars(
        select(Post.id).where(
            Post.author_user_id == user.user_id,
            Post.author_type != "system",
        )
    ).all()
    owned_comment_ids = session.scalars(
        select(Comment.id).where(Comment.author_user_id == user.user_id)
    ).all()
    conditions = [
        or_(
            (SafetyReport.target_type == "post") & SafetyReport.target_id.in_(owned_post_ids),
            (SafetyReport.target_type == "comment") & SafetyReport.target_id.in_(owned_comment_ids),
        )
    ]
    if status_filter:
        conditions.append(SafetyReport.status == status_filter)
    rows = session.scalars(
        select(SafetyReport).where(*conditions).order_by(SafetyReport.created_at.desc())
    ).all()
    return [ReportResponse.model_validate(row) for row in rows]


def _user_can_moderate_report(session: Session, report: SafetyReport, user_id: str) -> bool:
    if report.target_type == "post":
        return (
            session.scalar(
                select(func.count(Post.id)).where(
                    Post.id == report.target_id,
                    Post.author_user_id == user_id,
                    Post.author_type != "system",
                )
            )
            or 0
        ) > 0
    if report.target_type == "comment":
        return (
            session.scalar(
                select(func.count(Comment.id)).where(
                    Comment.id == report.target_id,
                    Comment.author_user_id == user_id,
                )
            )
            or 0
        ) > 0
    return False


@router.patch("/v1/moderation/reports/{report_id}", response_model=ReportResponse)
def decide_report(
    report_id: str,
    payload: ReportDecisionRequest,
    user: CurrentPrincipal,
    _: WriteQuota,
    session: DbSession,
) -> ReportResponse:
    report = session.get(SafetyReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    if not _user_can_moderate_report(session, report, user.user_id):
        raise HTTPException(status_code=403, detail="not authorized to decide this report")
    if payload.action:
        _apply_moderation_action(session, report, payload.action)
        _write_safety_audit(
            session,
            actor_user_id=user.user_id,
            action=f"moderation.{payload.action}",
            target_type=report.target_type,
            target_id=report.target_id,
            reason=report.reason,
            metadata={"report_id": report.id},
        )
    report.status = payload.status
    report.decision_note = payload.note
    _write_safety_audit(
        session,
        actor_user_id=user.user_id,
        action=f"report.{payload.status}",
        target_type=report.target_type,
        target_id=report.target_id,
        reason=report.reason,
        metadata={"report_id": report.id},
    )
    if payload.status in {"resolved", "dismissed"}:
        report.resolved_at = utc_now()
    session.commit()
    session.refresh(report)
    return ReportResponse.model_validate(report)


@router.get("/v1/safety/audit-log", response_model=list[SafetyAuditLogResponse])
def list_safety_audit_log(
    user: CurrentPrincipal, session: DbSession
) -> list[SafetyAuditLogResponse]:
    rows = session.scalars(
        select(SafetyAuditLog)
        .where(SafetyAuditLog.actor_user_id == user.user_id)
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


@router.get("/v1/feed", response_model=FeedResponse)
async def get_feed(
    user: CurrentPrincipal,
    session: DbSession,
    filter: Annotated[str, Query(pattern="^(all|posts)$")] = "all",
    before: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1)] = None,
) -> FeedResponse:
    followed_user_ids = await list_following_user_ids(settings, user.user_id)
    group_ids = set(
        session.scalars(
            select(GroupMembership.group_id).where(GroupMembership.user_id == user.user_id)
        ).all()
    )
    filters = []
    if followed_user_ids:
        filters.append(Post.author_user_id.in_(followed_user_ids))
    if group_ids:
        filters.append(Post.group_id.in_(group_ids))
    if not filters:
        return FeedResponse(items=[], next_before=None)
    conditions = [or_(*filters), Post.hidden_at.is_(None)]
    blocked_author_ids = _blocked_feed_author_ids(session, user.user_id)
    if blocked_author_ids:
        conditions.append(Post.author_user_id.not_in(blocked_author_ids))
    cursor_condition = _cursor_condition(Post, before)
    if cursor_condition is not None:
        conditions.append(cursor_condition)
    return _paginate_posts(
        select(Post).where(*conditions), session, _clamp_limit(limit), user.user_id
    )


@router.get("/v1/search/groups", response_model=list[GroupResponse])
def search_groups(q: str, session: DbSession) -> list[GroupResponse]:
    query = q.strip()
    if not query:
        return []
    groups = session.scalars(
        select(Group)
        .where(or_(Group.slug.icontains(query), Group.name.icontains(query)))
        .order_by(Group.official.desc(), Group.name)
        .limit(20)
    ).all()
    return [GroupResponse.model_validate(group) for group in groups]


@router.post("/v1/internal/anonymize-author", response_model=SimpleStatusResponse)
def anonymize_author(payload: AnonymizeAuthorRequest, session: DbSession) -> SimpleStatusResponse:
    posts = session.scalars(select(Post).where(Post.author_user_id == payload.user_id)).all()
    comments = session.scalars(
        select(Comment).where(Comment.author_user_id == payload.user_id)
    ).all()
    items: list[Post | Comment] = [*posts, *comments]
    for item in items:
        item.author_username = "deleted-user"
        item.author_display_name = "Deleted User"
        session.add(item)
    # GDPR: votes and emoji reactions are personal data keyed by user_id — hard delete.
    session.execute(delete(Reaction).where(Reaction.user_id == payload.user_id))
    session.execute(delete(CommentReaction).where(CommentReaction.user_id == payload.user_id))
    session.execute(delete(PostEmojiReaction).where(PostEmojiReaction.user_id == payload.user_id))
    session.commit()
    return SimpleStatusResponse(status="ok")
