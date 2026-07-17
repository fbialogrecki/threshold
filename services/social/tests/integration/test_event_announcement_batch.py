from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from social.api import routes
from social.domain.models import (
    Comment,
    EventAnnouncement,
    Group,
    Post,
    PostEmojiReaction,
    Reaction,
    UserBlock,
)
from social.main import app
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
VIEWER_HEADERS = {**TOKEN_HEADERS, "X-Threshold-User-Id": "viewer-1"}


def _announcement(
    session: Session,
    group: Group,
    event_id: str,
    event_slug: str,
    created_at: datetime,
    *,
    author_user_id: str = "event-system",
    author_type: str = "system",
    hidden: bool = False,
) -> Post:
    post = Post(
        author_user_id=author_user_id,
        author_username="threshold-events",
        author_display_name="Threshold Events",
        author_type=author_type,
        group_id=group.id,
        event_id=event_id,
        event_slug=event_slug,
        body=event_slug,
        created_at=created_at,
        hidden_at=created_at if hidden else None,
    )
    session.add(post)
    session.flush()
    session.add(
        EventAnnouncement(
            event_id=event_id,
            event_slug=event_slug,
            post_id=post.id,
            group_id=group.id,
            created_at=created_at,
        )
    )
    return post


def test_event_announcement_batch_requires_token_and_validates_bounds(session: Session) -> None:
    client = TestClient(app)
    path = "/internal/v1/event-announcements/batch"

    assert client.post(path, json={}).status_code == 401
    assert client.post(path, headers=TOKEN_HEADERS, json={}).status_code == 401
    assert client.post(path, headers=VIEWER_HEADERS, json={}).json() == {
        "posts": [],
        "represented_event_ids": [],
        "represented_event_slugs": [],
    }
    assert (
        client.post(
            path,
            headers=VIEWER_HEADERS,
            json={"event_ids": ["event"] * 100},
        ).status_code
        == 200
    )
    assert (
        client.post(
            path,
            headers=VIEWER_HEADERS,
            json={"event_ids": ["event"] * 101},
        ).status_code
        == 422
    )
    assert (
        client.post(
            path,
            headers=VIEWER_HEADERS,
            json={
                "event_ids": [f"event-{index}" for index in range(50)],
                "event_slugs": [f"event-{index}" for index in range(51)],
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            path,
            headers=VIEWER_HEADERS,
            json={"event_slugs": ["Unsafe Slug"]},
        ).status_code
        == 422
    )


def test_event_announcement_batch_represents_moderation_hidden_without_visible_post(
    session: Session,
) -> None:
    group = session.query(Group).filter_by(slug="techno-warsaw").one()
    older = _announcement(
        session,
        group,
        "event-old",
        "old-event",
        datetime(2026, 7, 1, tzinfo=UTC),
    )
    newer = _announcement(
        session,
        group,
        "event-new",
        "new-event",
        datetime(2026, 7, 2, tzinfo=UTC),
    )
    _announcement(
        session,
        group,
        "event-hidden",
        "hidden-event",
        datetime(2026, 7, 3, tzinfo=UTC),
        hidden=True,
    )
    session.add_all(
        [
            Reaction(post_id=newer.id, user_id="viewer-1", kind="up"),
            PostEmojiReaction(post_id=newer.id, user_id="viewer-1", emoji="🔥"),
            Comment(
                post_id=newer.id,
                author_user_id="commenter",
                author_username="commenter",
                author_display_name="Commenter",
                body="hello",
            ),
        ]
    )
    session.commit()
    selects: list[str] = []

    def capture_select(
        _connection: Connection,
        _cursor: object,
        statement: str,
        _parameters: Any,
        _context: object,
        _executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            selects.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", capture_select)
    try:
        response = TestClient(app).post(
            "/internal/v1/event-announcements/batch",
            headers=VIEWER_HEADERS,
            json={
                "event_ids": [
                    "event-old",
                    "event-hidden",
                    "event-new",
                    "missing",
                    "event-old",
                ],
                "event_slugs": ["new-event", "hidden-event"],
            },
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["posts"]] == [newer.id, older.id]
    assert body["represented_event_ids"] == [
        "event-old",
        "event-hidden",
        "event-new",
    ]
    assert body["represented_event_slugs"] == ["new-event", "hidden-event"]
    assert body["posts"][0]["event_id"] == "event-new"
    assert body["posts"][0]["event_slug"] == "new-event"
    assert body["posts"][0]["viewer_vote"] == "up"
    assert body["posts"][0]["comment_count"] == 1
    assert body["posts"][0]["emoji_reactions"] == [
        {"emoji": "🔥", "count": 1, "viewer_reacted": True}
    ]
    assert len(selects) == 9


def test_legacy_event_refs_selects_one_matching_deterministic_pair(session: Session) -> None:
    group = session.query(Group).filter_by(slug="techno-warsaw").one()
    post = Post(
        author_user_id="event-system",
        author_username="threshold-events",
        author_display_name="Threshold Events",
        author_type="system",
        group_id=group.id,
        body="legacy",
    )
    session.add(post)
    session.flush()
    session.add_all(
        [
            EventAnnouncement(
                id="row-z",
                event_id="event-z",
                event_slug="zebra-night",
                post_id=post.id,
                group_id=group.id,
                created_at=datetime(2026, 7, 1, tzinfo=UTC),
            ),
            EventAnnouncement(
                id="row-a",
                event_id="event-a",
                event_slug="alpha-night",
                post_id=post.id,
                group_id=group.id,
                created_at=datetime(2026, 7, 2, tzinfo=UTC),
            ),
        ]
    )
    session.commit()

    assert routes._legacy_event_refs(session, [post]) == {
        post.id: ("event-z", "zebra-night")
    }


def test_event_announcement_batch_filters_blocks_and_non_system_posts(session: Session) -> None:
    group = session.query(Group).filter_by(slug="techno-warsaw").one()
    visible = _announcement(
        session,
        group,
        "event-visible",
        "visible-event",
        datetime(2026, 7, 1, tzinfo=UTC),
        author_user_id="visible-creator",
    )
    _announcement(
        session,
        group,
        "event-blocked",
        "blocked-event",
        datetime(2026, 7, 2, tzinfo=UTC),
        author_user_id="blocked-creator",
    )
    _announcement(
        session,
        group,
        "event-blocker",
        "blocker-event",
        datetime(2026, 7, 3, tzinfo=UTC),
        author_user_id="blocking-creator",
    )
    _announcement(
        session,
        group,
        "event-ordinary",
        "ordinary-event",
        datetime(2026, 7, 4, tzinfo=UTC),
        author_user_id="ordinary-creator",
        author_type="user",
    )
    session.add_all(
        [
            UserBlock(blocker_user_id="viewer-1", blocked_user_id="blocked-creator"),
            UserBlock(blocker_user_id="blocking-creator", blocked_user_id="viewer-1"),
        ]
    )
    session.commit()

    response = TestClient(app).post(
        "/internal/v1/event-announcements/batch",
        headers=VIEWER_HEADERS,
        json={
            "event_ids": [
                "event-visible",
                "event-blocked",
                "event-blocker",
                "event-ordinary",
            ]
        },
    )
    other_viewer = TestClient(app).post(
        "/internal/v1/event-announcements/batch",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "viewer-2"},
        json={
            "event_ids": [
                "event-visible",
                "event-blocked",
                "event-blocker",
                "event-ordinary",
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [post["id"] for post in body["posts"]] == [visible.id]
    assert body["represented_event_ids"] == [
        "event-visible",
        "event-blocked",
        "event-blocker",
        "event-ordinary",
    ]
    assert [post["event_id"] for post in other_viewer.json()["posts"]] == [
        "event-blocker",
        "event-blocked",
        "event-visible",
    ]


def test_event_announcement_batch_caps_slug_collision_to_one_post(session: Session) -> None:
    group = session.query(Group).filter_by(slug="techno-warsaw").one()
    older = _announcement(
        session,
        group,
        "event-old",
        "shared-slug",
        datetime(2026, 7, 1, tzinfo=UTC),
    )
    _announcement(
        session,
        group,
        "event-new",
        "shared-slug",
        datetime(2026, 7, 2, tzinfo=UTC),
    )
    session.commit()

    response = TestClient(app).post(
        "/internal/v1/event-announcements/batch",
        headers=VIEWER_HEADERS,
        json={"event_slugs": ["shared-slug", "shared-slug"]},
    )

    assert response.status_code == 200
    assert [post["id"] for post in response.json()["posts"]] == [older.id]
    assert response.json()["represented_event_ids"] == []
    assert response.json()["represented_event_slugs"] == ["shared-slug"]


def test_event_announcement_batch_preserves_reference_order_without_identifier_leaks(
    session: Session,
) -> None:
    group = session.query(Group).filter_by(slug="techno-warsaw").one()
    first = _announcement(
        session,
        group,
        "event-first",
        "first-slug",
        datetime(2026, 7, 1, tzinfo=UTC),
    )
    second = _announcement(
        session,
        group,
        "event-second",
        "second-slug",
        datetime(2026, 7, 2, tzinfo=UTC),
    )
    session.commit()
    client = TestClient(app)

    id_only = client.post(
        "/internal/v1/event-announcements/batch",
        headers=VIEWER_HEADERS,
        json={"event_ids": ["event-second", "event-first", "event-second"]},
    ).json()
    slug_only = client.post(
        "/internal/v1/event-announcements/batch",
        headers=VIEWER_HEADERS,
        json={"event_slugs": ["first-slug"]},
    ).json()
    mismatch = client.post(
        "/internal/v1/event-announcements/batch",
        headers=VIEWER_HEADERS,
        json={"event_ids": ["event-first"], "event_slugs": ["second-slug"]},
    ).json()

    assert id_only["represented_event_ids"] == ["event-second", "event-first"]
    assert id_only["represented_event_slugs"] == []
    assert [post["id"] for post in id_only["posts"]] == [second.id, first.id]
    assert slug_only["represented_event_ids"] == []
    assert slug_only["represented_event_slugs"] == ["first-slug"]
    assert mismatch["represented_event_ids"] == ["event-first"]
    assert mismatch["represented_event_slugs"] == ["second-slug"]


def test_event_announcement_batch_dedupes_same_post_and_prevents_slug_starvation(
    session: Session,
) -> None:
    group = session.query(Group).filter_by(slug="techno-warsaw").one()
    shared_selected = _announcement(
        session,
        group,
        "event-shared-old",
        "shared-slug",
        datetime(2026, 7, 1, tzinfo=UTC),
    )
    _announcement(
        session,
        group,
        "event-shared-new",
        "shared-slug",
        datetime(2026, 7, 2, tzinfo=UTC),
    )
    other = _announcement(
        session,
        group,
        "event-other",
        "other-slug",
        datetime(2026, 7, 3, tzinfo=UTC),
    )
    session.commit()
    client = TestClient(app)

    same_post = client.post(
        "/internal/v1/event-announcements/batch",
        headers=VIEWER_HEADERS,
        json={
            "event_ids": ["event-shared-old"],
            "event_slugs": ["shared-slug"],
        },
    ).json()
    multiple_slugs = client.post(
        "/internal/v1/event-announcements/batch",
        headers=VIEWER_HEADERS,
        json={"event_slugs": ["shared-slug", "other-slug"]},
    ).json()

    assert [post["id"] for post in same_post["posts"]] == [shared_selected.id]
    assert same_post["represented_event_ids"] == ["event-shared-old"]
    assert same_post["represented_event_slugs"] == ["shared-slug"]
    assert multiple_slugs["represented_event_slugs"] == ["shared-slug", "other-slug"]
    assert [post["id"] for post in multiple_slugs["posts"]] == [
        other.id,
        shared_selected.id,
    ]


def test_event_announcement_batch_exposes_events_service_admitted_posts_without_membership(
    session: Session,
) -> None:
    out_of_city_group = Group(
        slug="out-of-city-group",
        name="Out Of City Group",
        city="Berlin",
        official=True,
    )
    session.add(out_of_city_group)
    session.flush()
    followed_page = _announcement(
        session,
        out_of_city_group,
        "event-followed-page",
        "followed-page-event",
        datetime(2026, 7, 1, tzinfo=UTC),
    )
    followed_organizer = _announcement(
        session,
        out_of_city_group,
        "event-followed-organizer",
        "followed-organizer-event",
        datetime(2026, 7, 2, tzinfo=UTC),
    )
    followed_event = _announcement(
        session,
        out_of_city_group,
        "event-followed-directly",
        "followed-directly-event",
        datetime(2026, 7, 3, tzinfo=UTC),
    )
    session.commit()

    response = TestClient(app).post(
        "/internal/v1/event-announcements/batch",
        headers=VIEWER_HEADERS,
        json={
            "event_ids": [
                "event-followed-page",
                "event-followed-organizer",
                "event-followed-directly",
            ]
        },
    )

    assert response.status_code == 200
    assert [post["id"] for post in response.json()["posts"]] == [
        followed_event.id,
        followed_organizer.id,
        followed_page.id,
    ]
    assert response.json()["represented_event_ids"] == [
        "event-followed-page",
        "event-followed-organizer",
        "event-followed-directly",
    ]
