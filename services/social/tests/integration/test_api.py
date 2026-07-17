import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from social.api import routes
from social.domain.models import (
    EventAnnouncement,
    Group,
    Post,
    SafetyAuditLog,
    SafetyReport,
    UserBlock,
    utc_now,
)
from social.main import app
from social.mentions import extract_mention_candidates
from social.nats_server import apply_user_block_event
from sqlalchemy import event, select
from sqlalchemy.orm import Session

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
USER_HEADERS = {
    **TOKEN_HEADERS,
    "X-Threshold-User-Id": "user-1",
    "X-Threshold-Username": "nightcrawler",
    "X-Threshold-Display-Name": "Night Crawler",
}
USER_2_HEADERS = {
    **TOKEN_HEADERS,
    "X-Threshold-User-Id": "user-2",
    "X-Threshold-Username": "warper",
    "X-Threshold-Display-Name": "Warper",
}


def test_healthz() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "social"}


def test_readyz_checks_database(session: Session) -> None:
    client = TestClient(app)
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "social"}


def test_social_reads_require_internal_token(session: Session) -> None:
    client = TestClient(app)
    response = client.get("/v1/groups")
    assert response.status_code == 401

    response = client.get("/v1/groups", headers={"X-Threshold-Internal-Token": "wrong"})
    assert response.status_code == 401

    response = client.get("/v1/groups", headers=TOKEN_HEADERS)
    assert response.status_code == 200
    assert response.json()[0]["slug"] == "techno-warsaw"


def test_internal_capabilities_requires_token_and_has_stable_shape(session: Session) -> None:
    client = TestClient(app)

    unauthorized = client.get("/internal/v1/capabilities")
    authorized = client.get("/internal/v1/capabilities", headers=TOKEN_HEADERS)

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {"event_post_contract": 1}


def test_extract_mention_candidates_ignores_email_urls_and_codeish_tokens() -> None:
    text = "Ping @nightcrawler and #rave-night, not me@example.test, https://x/@ghost or `@code`."

    candidates = extract_mention_candidates(text)

    assert [(c.kind, c.handle) for c in candidates] == [
        ("profile", "nightcrawler"),
        ("event", "rave-night"),
    ]


def test_writes_require_user_id(session: Session) -> None:
    client = TestClient(app)
    response = client.post("/v1/groups/techno-warsaw/membership", headers=TOKEN_HEADERS)
    assert response.status_code == 401


def test_group_posts_require_membership(session: Session) -> None:
    client = TestClient(app)

    forbidden = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"group_slug": "techno-warsaw", "body": "not a member"},
    )
    assert forbidden.status_code == 403

    join = client.post("/v1/groups/techno-warsaw/membership", headers=USER_HEADERS)
    assert join.status_code == 200

    allowed = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"group_slug": "techno-warsaw", "body": "member post"},
    )
    assert allowed.status_code == 201


def test_group_post_comment_reaction_and_anonymize_flow(session: Session) -> None:
    client = TestClient(app)

    join = client.post("/v1/groups/techno-warsaw/membership", headers=USER_HEADERS)
    assert join.status_code == 200

    post_response = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={
            "group_slug": "techno-warsaw",
            "body": "first post",
        },
    )
    assert post_response.status_code == 201
    post = post_response.json()
    assert post["author_username"] == "nightcrawler"
    assert post["mentions"] == []
    assert post["like_count"] == 0
    assert post["comment_count"] == 0

    like_response = client.put(
        f"/v1/posts/{post['id']}/reaction",
        headers=USER_HEADERS,
        json={"kind": "like"},
    )
    assert like_response.status_code == 200
    assert like_response.json() == {"status": "ok"}

    comment_response = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_HEADERS,
        json={"body": "yes"},
    )
    assert comment_response.status_code == 201
    assert comment_response.json()["author_display_name"] == "Night Crawler"

    feed_response = client.get("/v1/feed", headers=USER_HEADERS)
    assert feed_response.status_code == 200
    assert [item["id"] for item in feed_response.json()["items"]] == [post["id"]]

    anonymize_response = client.post(
        "/v1/internal/anonymize-author",
        headers=TOKEN_HEADERS,
        json={"user_id": "user-1"},
    )
    assert anonymize_response.status_code == 200

    updated = client.get(f"/v1/posts/{post['id']}", headers=TOKEN_HEADERS).json()
    assert updated["author_username"] == "deleted-user"
    assert updated["author_display_name"] == "Deleted User"


def test_membership_and_reaction_are_idempotent(session: Session) -> None:
    client = TestClient(app)

    first_join = client.post("/v1/groups/techno-warsaw/membership", headers=USER_HEADERS)
    second_join = client.post("/v1/groups/techno-warsaw/membership", headers=USER_HEADERS)
    assert first_join.status_code == 200
    assert second_join.status_code == 200

    post = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"group_slug": "techno-warsaw", "body": "idempotent like"},
    ).json()
    first_like = client.put(
        f"/v1/posts/{post['id']}/reaction",
        headers=USER_HEADERS,
        json={"kind": "like"},
    )
    second_like = client.put(
        f"/v1/posts/{post['id']}/reaction",
        headers=USER_HEADERS,
        json={"kind": "like"},
    )
    assert first_like.status_code == 200
    assert second_like.status_code == 200
    assert client.get(f"/v1/posts/{post['id']}", headers=TOKEN_HEADERS).json()["like_count"] == 1


def test_feed_filter_and_cursor_contract(session: Session) -> None:
    client = TestClient(app)
    client.post("/v1/groups/techno-warsaw/membership", headers=USER_HEADERS)
    first = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"group_slug": "techno-warsaw", "body": "first"},
    ).json()
    second = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"group_slug": "techno-warsaw", "body": "second"},
    ).json()

    invalid_cursor = client.get(
        "/v1/feed?before=not-a-cursor",
        headers=USER_HEADERS,
    )
    assert invalid_cursor.status_code == 400

    invalid_filter = client.get("/v1/feed?filter=events", headers=USER_HEADERS)
    assert invalid_filter.status_code == 422

    first_page = client.get("/v1/feed?filter=posts&limit=1", headers=USER_HEADERS)
    assert first_page.status_code == 200
    body = first_page.json()
    assert [item["id"] for item in body["items"]] == [second["id"]]
    assert body["next_before"] is not None

    second_page = client.get(f"/v1/feed?limit=1&before={body['next_before']}", headers=USER_HEADERS)
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == [first["id"]]


def test_ordinary_and_event_linked_posts_expose_event_reference(session: Session) -> None:
    client = TestClient(app)
    client.post("/v1/groups/techno-warsaw/membership", headers=USER_HEADERS)

    ordinary = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"group_slug": "techno-warsaw", "body": "ordinary post"},
    )
    linked = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={
            "group_slug": "techno-warsaw",
            "event_id": "event-1",
            "event_slug": " Warehouse-Signal ",
            "body": "linked post",
        },
    )

    assert ordinary.status_code == 201
    assert ordinary.json()["event_id"] is None
    assert ordinary.json()["event_slug"] is None
    assert linked.status_code == 201
    assert linked.json()["event_id"] == "event-1"
    assert linked.json()["event_slug"] == "warehouse-signal"
    linked_id = linked.json()["id"]
    linked_row = session.get(Post, linked_id)
    assert linked_row is not None
    assert linked_row.event_id == "event-1"
    assert linked_row.event_slug == "warehouse-signal"
    assert (
        client.get(f"/v1/posts/{linked_id}", headers=TOKEN_HEADERS).json()["event_slug"]
        == "warehouse-signal"
    )
    feed = client.get("/v1/feed", headers=USER_HEADERS).json()["items"]
    assert {item["id"]: item["event_slug"] for item in feed} == {
        ordinary.json()["id"]: None,
        linked_id: "warehouse-signal",
    }


def test_post_event_reference_pair_and_attachment_mode_validation(session: Session) -> None:
    client = TestClient(app)

    only_id = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "missing slug", "event_id": "event-1"},
    )
    only_slug = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "missing ID", "event_slug": "warehouse-signal"},
    )
    image_and_event = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={
            "body": "two attachments",
            "event_id": "event-1",
            "event_slug": "warehouse-signal",
            "media_asset_ids": ["image-1"],
        },
    )

    assert only_id.status_code == 422
    assert only_slug.status_code == 422
    assert image_and_event.status_code == 422


def test_versioned_event_post_endpoint_validates_before_mutation(session: Session) -> None:
    client = TestClient(app)
    payload = {
        "body": "versioned event post",
        "event_id": "event-1",
        "event_slug": "warehouse-signal",
    }

    assert client.post("/v1/event-posts", json=payload).status_code == 401
    assert (
        client.post("/v1/event-posts", headers=TOKEN_HEADERS, json=payload).status_code
        == 401
    )
    before = session.query(Post).count()
    no_event = client.post(
        "/v1/event-posts",
        headers=USER_HEADERS,
        json={"body": "missing event"},
    )
    media = client.post(
        "/v1/event-posts",
        headers=USER_HEADERS,
        json={**payload, "media_asset_ids": ["image-1"]},
    )
    unsupported = client.post(
        "/v1/event-posts-v2",
        headers=USER_HEADERS,
        json=payload,
    )

    assert no_event.status_code == 422
    assert media.status_code == 422
    assert unsupported.status_code == 404
    assert session.query(Post).count() == before

    created = client.post("/v1/event-posts", headers=USER_HEADERS, json=payload)
    assert created.status_code == 201
    assert created.json()["event_id"] == "event-1"
    assert created.json()["event_slug"] == "warehouse-signal"
    assert created.json()["media_asset_ids"] == []


def test_internal_event_announcement_crossposts_once_to_official_city_group(
    session: Session,
) -> None:
    client = TestClient(app)

    payload = {
        "event_id": "event-1",
        "event_slug": "warehouse-signal",
        "event_title": "Warehouse Signal",
        "city": "Warsaw",
        "page_id": "page-1",
        "actor_user_id": "user-1",
    }

    first = client.post("/internal/v1/event-announcements", headers=TOKEN_HEADERS, json=payload)
    second = client.post("/internal/v1/event-announcements", headers=TOKEN_HEADERS, json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["event_id"] == "event-1"
    assert first.json()["event_slug"] == "warehouse-signal"

    group = session.query(Group).filter_by(slug="techno-warsaw").one()
    posts = session.query(Post).filter_by(group_id=group.id).all()
    assert len(posts) == 1
    post = posts[0]
    assert post.author_type == "system"
    assert post.event_id == "event-1"
    assert post.event_slug == "warehouse-signal"
    assert "Warehouse Signal" in post.body
    assert "/events/warehouse-signal" in post.body

    assert (
        client.post(
            f"/v1/posts/{post.id}/comments", headers=USER_2_HEADERS, json={"body": "see you there"}
        ).status_code
        == 201
    )
    assert (
        client.put(
            f"/v1/posts/{post.id}/reaction", headers=USER_HEADERS, json={"kind": "up"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/v1/posts/{post.id}/reaction", headers=USER_2_HEADERS, json={"kind": "down"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/v1/posts/{post.id}/emoji", headers=USER_HEADERS, json={"emoji": "🔥"}
        ).status_code
        == 200
    )
    response = client.get(f"/v1/posts/{post.id}", headers=USER_HEADERS).json()
    assert response["event_slug"] == "warehouse-signal"
    assert response["viewer_is_author"] is False
    assert response["comment_count"] == 1
    assert (response["up_count"], response["down_count"], response["viewer_vote"]) == (1, 1, "up")
    assert response["emoji_reactions"] == [{"emoji": "🔥", "count": 1, "viewer_reacted": True}]
    assert (
        client.patch(
            f"/v1/posts/{post.id}", headers=USER_HEADERS, json={"body": "changed"}
        ).status_code
        == 403
    )
    assert client.delete(f"/v1/posts/{post.id}", headers=USER_HEADERS).status_code == 403

    report = client.post(
        "/v1/reports",
        headers=USER_2_HEADERS,
        json={"target_type": "post", "target_id": post.id, "reason": "spam"},
    )
    assert report.status_code == 201
    assert client.get("/v1/moderation/reports", headers=USER_HEADERS).json() == []
    assert (
        client.patch(
            f"/v1/moderation/reports/{report.json()['id']}",
            headers=USER_HEADERS,
            json={"status": "resolved", "action": "delete"},
        ).status_code
        == 403
    )
    report_row = session.get(SafetyReport, report.json()["id"])
    assert report_row is not None
    with pytest.raises(HTTPException, match="system posts cannot be deleted"):
        routes._apply_moderation_action(session, report_row, "delete")
    assert session.get(Post, post.id) is post

    post.event_id = None
    post.event_slug = None
    session.commit()
    legacy = client.get(f"/v1/posts/{post.id}", headers=TOKEN_HEADERS).json()
    assert legacy["event_id"] == "event-1"
    assert legacy["event_slug"] == "warehouse-signal"


def test_feed_batches_legacy_event_slug_fallback(session: Session) -> None:
    client = TestClient(app)
    client.post("/v1/groups/techno-warsaw/membership", headers=USER_HEADERS)
    group = session.query(Group).filter_by(slug="techno-warsaw").one()
    expected: dict[str, str] = {}
    for index in range(3):
        post = Post(
            author_user_id="event-system",
            author_username="threshold-events",
            author_display_name="Threshold Events",
            author_type="system",
            group_id=group.id,
            event_id=None,
            event_slug=None,
            body=f"Legacy event {index}",
        )
        session.add(post)
        session.flush()
        slug = f"legacy-event-{index}"
        expected[post.id] = slug
        session.add(
            EventAnnouncement(
                event_id=f"event-{index}",
                event_slug=slug,
                post_id=post.id,
                group_id=group.id,
            )
        )
    session.commit()

    event_queries = 0

    def count_event_queries(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        nonlocal event_queries
        if statement.lstrip().lower().startswith("select") and "event_announcements" in statement:
            event_queries += 1

    bind = session.get_bind()
    event.listen(bind, "before_cursor_execute", count_event_queries)
    try:
        response = client.get("/v1/feed", headers=USER_HEADERS)
    finally:
        event.remove(bind, "before_cursor_execute", count_event_queries)

    assert response.status_code == 200
    assert {item["id"]: item["event_slug"] for item in response.json()["items"]} == expected
    assert event_queries == 1


def test_internal_event_announcement_missing_city_group_returns_404(session: Session) -> None:
    response = TestClient(app).post(
        "/internal/v1/event-announcements",
        headers=TOKEN_HEADERS,
        json={
            "event_id": "event-2",
            "event_slug": "missing-group-event",
            "event_title": "Missing Group Event",
            "city": "Berlin",
            "page_id": "page-1",
            "actor_user_id": "user-1",
        },
    )

    assert response.status_code == 404
    assert session.query(Post).count() == 0


def test_write_payloads_reject_html_and_blank_body(session: Session) -> None:
    client = TestClient(app)

    html_post = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "<script>alert('xss')</script>"},
    )
    assert html_post.status_code == 422

    blank_post = client.post("/v1/posts", headers=USER_HEADERS, json={"body": "   "})
    assert blank_post.status_code == 422

    unsafe_event_slug = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "unsafe event", "event_slug": "../warehouse"},
    )
    assert unsafe_event_slug.status_code == 422

    short_event_slug = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "short event", "event_slug": " a "},
    )
    assert short_event_slug.status_code == 422

    long_event_slug = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "long event", "event_slug": f" {'a' * 161} "},
    )
    assert long_event_slug.status_code == 422

    post = client.post("/v1/posts", headers=USER_HEADERS, json={"body": "safe"}).json()
    html_comment = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_HEADERS,
        json={"body": "<b>nope</b>"},
    )
    assert html_comment.status_code == 422


def _create_post(client: TestClient, body: str = "vote target") -> dict[str, object]:
    response = client.post("/v1/posts", headers=USER_HEADERS, json={"body": body})
    assert response.status_code == 201
    payload: dict[str, object] = response.json()
    return payload


def test_post_auto_resolves_mentions_and_emits_user_notification(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    notifications: list[dict[str, object]] = []

    async def fake_resolve_profile(_settings: object, handle: str) -> dict[str, str]:
        assert handle == "warper"
        return {
            "target_type": "user",
            "target_id": "user-2",
            "handle": "warper",
            "display_name": "Warper",
            "target_url": "/profiles/warper",
            "recipient_user_id": "user-2",
        }

    async def fake_resolve_event(_settings: object, slug: str) -> dict[str, str]:
        assert slug == "rave-night"
        return {
            "target_type": "event",
            "target_id": "event-1",
            "handle": "rave-night",
            "display_name": "Rave Night",
            "target_url": "/events/rave-night",
        }

    async def fake_create_notification(_settings: object, **kwargs: object) -> None:
        notifications.append(kwargs)

    monkeypatch.setattr(routes, "resolve_profile_or_page_mention", fake_resolve_profile)
    monkeypatch.setattr(routes, "resolve_event_mention", fake_resolve_event)
    monkeypatch.setattr(routes, "create_notification", fake_create_notification)

    response = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "hello @warper, see #rave-night"},
    )

    assert response.status_code == 201
    post = response.json()
    assert post["mentions"] == [
        {
            "mention_type": "user",
            "target_handle": "warper",
            "target_id": "user-2",
            "display_name": "Warper",
            "target_url": "/profiles/warper",
            "start_index": 6,
            "end_index": 13,
        },
        {
            "mention_type": "event",
            "target_handle": "rave-night",
            "target_id": "event-1",
            "display_name": "Rave Night",
            "target_url": "/events/rave-night",
            "start_index": 19,
            "end_index": 30,
        },
    ]
    assert notifications == [
        {
            "recipient_user_id": "user-2",
            "actor_user_id": "user-1",
            "event_type": "mention.created",
            "target_type": "post",
            "target_id": post["id"],
            "target_url": f"/posts/{post['id']}",
            "title": "Night Crawler mentioned you",
            "dedupe_key": f"mention:post:{post['id']}:user-2",
            "metadata": {
                "mention_type": "user",
                "handle": "warper",
                "actor_username": "nightcrawler",
                "actor_display_name": "Night Crawler",
            },
        }
    ]


def test_unknown_mention_target_rejects_post(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)

    async def missing_profile(_settings: object, handle: str) -> None:
        return None

    monkeypatch.setattr(routes, "resolve_profile_or_page_mention", missing_profile)

    response = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "hello @missinguser"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "mention target not found"


def test_comment_auto_resolves_mentions(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    post = _create_post(client)
    notifications: list[dict[str, object]] = []

    async def fake_resolve_profile(_settings: object, handle: str) -> dict[str, str]:
        return {
            "target_type": "user",
            "target_id": "user-2",
            "handle": handle,
            "display_name": "Warper",
            "target_url": f"/profiles/{handle}",
            "recipient_user_id": "user-2",
        }

    async def fake_create_notification(_settings: object, **kwargs: object) -> None:
        notifications.append(kwargs)

    monkeypatch.setattr(routes, "resolve_profile_or_page_mention", fake_resolve_profile)
    monkeypatch.setattr(routes, "create_notification", fake_create_notification)

    response = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_HEADERS,
        json={"body": "reply @warper"},
    )

    assert response.status_code == 201
    comment = response.json()
    assert comment["mentions"] == [
        {
            "mention_type": "user",
            "target_handle": "warper",
            "target_id": "user-2",
            "display_name": "Warper",
            "target_url": "/profiles/warper",
            "start_index": 6,
            "end_index": 13,
        }
    ]
    mention_notifications = [
        item for item in notifications if item["event_type"] == "mention.created"
    ]
    assert mention_notifications[0]["target_type"] == "comment"
    assert mention_notifications[0]["target_id"] == comment["id"]


def test_mass_mentions_are_limited(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)

    async def fake_resolve_profile(_settings: object, handle: str) -> dict[str, str]:
        return {
            "target_type": "user",
            "target_id": f"id-{handle}",
            "handle": handle,
            "display_name": handle,
            "target_url": f"/profiles/{handle}",
            "recipient_user_id": f"id-{handle}",
        }

    monkeypatch.setattr(routes, "resolve_profile_or_page_mention", fake_resolve_profile)
    body = " ".join(f"@user{i}" for i in range(11))

    response = client.post("/v1/posts", headers=USER_HEADERS, json={"body": body})

    assert response.status_code == 422
    assert response.json()["detail"] == "too many mentions"


def test_post_votes_up_down_change_and_viewer_state(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)

    up = client.put(f"/v1/posts/{post['id']}/reaction", headers=USER_HEADERS, json={"kind": "up"})
    assert up.status_code == 200
    down_other = client.put(
        f"/v1/posts/{post['id']}/reaction", headers=USER_2_HEADERS, json={"kind": "down"}
    )
    assert down_other.status_code == 200

    as_user_1 = client.get(f"/v1/posts/{post['id']}", headers=USER_HEADERS).json()
    assert as_user_1["up_count"] == 1
    assert as_user_1["down_count"] == 1
    assert as_user_1["viewer_vote"] == "up"
    assert as_user_1["like_count"] == 1

    as_anonymous = client.get(f"/v1/posts/{post['id']}", headers=TOKEN_HEADERS).json()
    assert as_anonymous["viewer_vote"] is None

    # Changing the vote updates the existing row instead of adding a second one.
    change = client.put(
        f"/v1/posts/{post['id']}/reaction", headers=USER_HEADERS, json={"kind": "down"}
    )
    assert change.status_code == 200
    changed = client.get(f"/v1/posts/{post['id']}", headers=USER_HEADERS).json()
    assert changed["up_count"] == 0
    assert changed["down_count"] == 2
    assert changed["viewer_vote"] == "down"

    removed = client.delete(f"/v1/posts/{post['id']}/reaction", headers=USER_HEADERS)
    assert removed.status_code == 204
    final = client.get(f"/v1/posts/{post['id']}", headers=USER_HEADERS).json()
    assert final["down_count"] == 1
    assert final["viewer_vote"] is None

    invalid = client.put(
        f"/v1/posts/{post['id']}/reaction", headers=USER_HEADERS, json={"kind": "meh"}
    )
    assert invalid.status_code == 422


def test_like_kind_is_accepted_as_up_alias(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)

    legacy = client.put(
        f"/v1/posts/{post['id']}/reaction", headers=USER_HEADERS, json={"kind": "like"}
    )
    assert legacy.status_code == 200

    body = client.get(f"/v1/posts/{post['id']}", headers=USER_HEADERS).json()
    assert body["up_count"] == 1
    assert body["viewer_vote"] == "up"


def test_report_queue_and_moderation_hide_flow(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client, "report target")
    comment = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_2_HEADERS,
        json={"body": "bad reply"},
    ).json()

    report = client.post(
        "/v1/reports",
        headers=USER_HEADERS,
        json={
            "target_type": "comment",
            "target_id": comment["id"],
            "reason": "harassment",
            "note": "please check",
        },
    )
    assert report.status_code == 201
    assert report.json()["status"] == "open"

    queue = client.get("/v1/moderation/reports", headers=USER_2_HEADERS)
    assert queue.status_code == 200
    item = queue.json()[0]
    assert item["target_type"] == "comment"
    assert item["reason"] == "harassment"
    assert "reporter_user_id" not in item
    assert "reporter_username" not in item
    assert "email" not in str(item).lower()

    decision = client.patch(
        f"/v1/moderation/reports/{item['id']}",
        headers=USER_2_HEADERS,
        json={"status": "resolved", "action": "hide", "note": "confirmed"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "resolved"

    comments = client.get(f"/v1/posts/{post['id']}/comments", headers=TOKEN_HEADERS).json()
    assert [row["id"] for row in comments] == []


def test_only_content_owner_can_decide_moderation_report(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client, "owned target")
    report = client.post(
        "/v1/reports",
        headers=USER_2_HEADERS,
        json={"target_type": "post", "target_id": post["id"], "reason": "spam"},
    )
    assert report.status_code == 201
    report_id = report.json()["id"]

    wrong_user = client.patch(
        f"/v1/moderation/reports/{report_id}",
        headers=USER_2_HEADERS,
        json={"status": "resolved", "action": "hide"},
    )
    assert wrong_user.status_code == 403

    owner = client.patch(
        f"/v1/moderation/reports/{report_id}",
        headers=USER_HEADERS,
        json={"status": "resolved", "action": "hide"},
    )
    assert owner.status_code == 200
    assert owner.json()["status"] == "resolved"


def test_reports_accept_public_profile_and_page_targets(session: Session) -> None:
    client = TestClient(app)

    profile_report = client.post(
        "/v1/reports",
        headers=USER_HEADERS,
        json={"target_type": "profile", "target_id": "nightcrawler", "reason": "impersonation"},
    )
    page_report = client.post(
        "/v1/reports",
        headers=USER_HEADERS,
        json={"target_type": "page", "target_id": "club-x", "reason": "spam"},
    )

    assert profile_report.status_code == 201
    assert page_report.status_code == 201
    assert "reporter_user_id" not in profile_report.json()
    assert "reporter_user_id" not in page_report.json()


def test_block_prevents_comments_mentions_and_notifications_for_blocker(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client, "block-owned post")

    block = client.post(
        "/v1/blocks/user-2",
        headers=USER_HEADERS,
        json={"blocked_username": "warper"},
    )
    assert block.status_code == 200

    blocked_comment = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_2_HEADERS,
        json={"body": "let me in"},
    )
    assert blocked_comment.status_code == 403

    blocked_mention = client.post(
        "/v1/posts",
        headers=USER_2_HEADERS,
        json={
            "body": "hey @nightcrawler",
            "mentions": [{"mention_type": "user", "target_handle": "nightcrawler"}],
        },
    )
    assert blocked_mention.status_code == 403

    visible_post = client.get(f"/v1/posts/{post['id']}", headers=USER_HEADERS).json()
    assert visible_post["comment_count"] == 0


def test_user_block_projection_events_update_local_enforcement_table(session: Session) -> None:
    apply_user_block_event(
        session,
        {
            "action": "blocked",
            "blocker_user_id": "user-1",
            "blocker_username": "nightcrawler",
            "blocked_user_id": "user-2",
            "blocked_username": "warper",
        },
    )
    session.commit()

    block = session.scalar(select(UserBlock).where(UserBlock.blocker_user_id == "user-1"))
    assert block is not None
    assert block.blocker_username == "nightcrawler"
    assert block.blocked_user_id == "user-2"

    apply_user_block_event(
        session,
        {
            "action": "unblocked",
            "blocker_user_id": "user-1",
            "blocked_user_id": "user-2",
        },
    )
    session.commit()

    assert session.scalar(select(UserBlock).where(UserBlock.blocker_user_id == "user-1")) is None


def test_comment_votes_and_viewer_state(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)
    comment = client.post(
        f"/v1/posts/{post['id']}/comments", headers=USER_HEADERS, json={"body": "hot take"}
    ).json()

    up = client.put(
        f"/v1/comments/{comment['id']}/reaction", headers=USER_2_HEADERS, json={"kind": "up"}
    )
    assert up.status_code == 200
    down = client.put(
        f"/v1/comments/{comment['id']}/reaction", headers=USER_HEADERS, json={"kind": "down"}
    )
    assert down.status_code == 200

    listed = client.get(f"/v1/posts/{post['id']}/comments", headers=USER_2_HEADERS).json()
    assert listed[0]["up_count"] == 1
    assert listed[0]["down_count"] == 1
    assert listed[0]["viewer_vote"] == "up"

    removed = client.delete(f"/v1/comments/{comment['id']}/reaction", headers=USER_2_HEADERS)
    assert removed.status_code == 204
    listed_again = client.get(f"/v1/posts/{post['id']}/comments", headers=USER_2_HEADERS).json()
    assert listed_again[0]["up_count"] == 0
    assert listed_again[0]["viewer_vote"] is None

    missing = client.put("/v1/comments/nope/reaction", headers=USER_HEADERS, json={"kind": "up"})
    assert missing.status_code == 404


def test_comment_replies_are_limited_to_one_level(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)
    other_post = _create_post(client, body="other thread")

    top = client.post(
        f"/v1/posts/{post['id']}/comments", headers=USER_HEADERS, json={"body": "top-level"}
    ).json()
    assert top["parent_id"] is None

    reply = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_2_HEADERS,
        json={"body": "nightcrawler agreed", "parent_id": top["id"]},
    )
    assert reply.status_code == 201
    assert reply.json()["parent_id"] == top["id"]

    # Reply to a reply is allowed: second level of nesting.
    nested = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_HEADERS,
        json={"body": "second level", "parent_id": reply.json()["id"]},
    )
    assert nested.status_code == 201
    assert nested.json()["parent_id"] == reply.json()["id"]

    # A third level is rejected: depth is capped server-side at two.
    too_deep = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_2_HEADERS,
        json={"body": "too deep", "parent_id": nested.json()["id"]},
    )
    assert too_deep.status_code == 400

    # Parent must belong to the same post.
    cross_post = client.post(
        f"/v1/posts/{other_post['id']}/comments",
        headers=USER_HEADERS,
        json={"body": "wrong thread", "parent_id": top["id"]},
    )
    assert cross_post.status_code == 400

    missing_parent = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_HEADERS,
        json={"body": "ghost", "parent_id": "does-not-exist"},
    )
    assert missing_parent.status_code == 400

    # Replies count toward the post comment counter.
    body = client.get(f"/v1/posts/{post['id']}", headers=TOKEN_HEADERS).json()
    assert body["comment_count"] == 3


def test_emoji_reactions_toggle_validation_and_limit(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)

    added = client.put(f"/v1/posts/{post['id']}/emoji", headers=USER_HEADERS, json={"emoji": "🔥"})
    assert added.status_code == 200
    again = client.put(f"/v1/posts/{post['id']}/emoji", headers=USER_HEADERS, json={"emoji": "🔥"})
    assert again.status_code == 200
    other_user = client.put(
        f"/v1/posts/{post['id']}/emoji", headers=USER_2_HEADERS, json={"emoji": "🔥"}
    )
    assert other_user.status_code == 200
    zwj_sequence = client.put(
        f"/v1/posts/{post['id']}/emoji",
        headers=USER_2_HEADERS,
        json={"emoji": "👨‍👩‍👧‍👦"},
    )
    assert zwj_sequence.status_code == 200

    body = client.get(f"/v1/posts/{post['id']}", headers=USER_HEADERS).json()
    reactions = {item["emoji"]: item for item in body["emoji_reactions"]}
    assert reactions["🔥"]["count"] == 2
    assert reactions["🔥"]["viewer_reacted"] is True
    assert reactions["👨‍👩‍👧‍👦"]["count"] == 1
    assert reactions["👨‍👩‍👧‍👦"]["viewer_reacted"] is False

    # Arbitrary text is rejected: chips render for other users.
    for invalid in ["x", "lol", "🔥🔥", "<b>", " ", "1"]:
        rejected = client.put(
            f"/v1/posts/{post['id']}/emoji", headers=USER_HEADERS, json={"emoji": invalid}
        )
        assert rejected.status_code == 422, invalid

    removed = client.delete(f"/v1/posts/{post['id']}/emoji?emoji=🔥", headers=USER_HEADERS)
    assert removed.status_code == 204
    body = client.get(f"/v1/posts/{post['id']}", headers=USER_HEADERS).json()
    reactions = {item["emoji"]: item for item in body["emoji_reactions"]}
    assert reactions["🔥"]["count"] == 1
    assert reactions["🔥"]["viewer_reacted"] is False


def test_emoji_distinct_limit_returns_409(session: Session) -> None:
    from social.main_dependencies import settings

    settings.write_rate_limit_count = 100
    client = TestClient(app)
    post = _create_post(client)

    emojis = [chr(codepoint) for codepoint in range(0x1F600, 0x1F600 + 20)]
    for emoji in emojis:
        response = client.put(
            f"/v1/posts/{post['id']}/emoji", headers=USER_HEADERS, json={"emoji": emoji}
        )
        assert response.status_code == 200, emoji

    over_limit = client.put(
        f"/v1/posts/{post['id']}/emoji", headers=USER_HEADERS, json={"emoji": "🔥"}
    )
    assert over_limit.status_code == 409

    # An emoji already on the post is still toggleable for another user.
    existing = client.put(
        f"/v1/posts/{post['id']}/emoji", headers=USER_2_HEADERS, json={"emoji": emojis[0]}
    )
    assert existing.status_code == 200


def test_anonymize_removes_votes_and_emoji(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)
    comment = client.post(
        f"/v1/posts/{post['id']}/comments", headers=USER_2_HEADERS, json={"body": "hi"}
    ).json()

    client.put(f"/v1/posts/{post['id']}/reaction", headers=USER_HEADERS, json={"kind": "up"})
    client.put(
        f"/v1/comments/{comment['id']}/reaction", headers=USER_HEADERS, json={"kind": "down"}
    )
    client.put(f"/v1/posts/{post['id']}/emoji", headers=USER_HEADERS, json={"emoji": "🖤"})

    anonymized = client.post(
        "/v1/internal/anonymize-author", headers=TOKEN_HEADERS, json={"user_id": "user-1"}
    )
    assert anonymized.status_code == 200

    body = client.get(f"/v1/posts/{post['id']}", headers=USER_HEADERS).json()
    assert body["up_count"] == 0
    assert body["emoji_reactions"] == []
    comments = client.get(f"/v1/posts/{post['id']}/comments", headers=USER_HEADERS).json()
    assert comments[0]["down_count"] == 0


def test_owner_can_edit_post_and_comment(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)

    forbidden = client.patch(
        f"/v1/posts/{post['id']}", headers=USER_2_HEADERS, json={"body": "hijack"}
    )
    assert forbidden.status_code == 403

    edited = client.patch(
        f"/v1/posts/{post['id']}", headers=USER_HEADERS, json={"body": "edited body"}
    )
    assert edited.status_code == 200
    assert edited.json()["body"] == "edited body"
    assert edited.json()["edited_at"] is not None
    assert edited.json()["viewer_is_author"] is True

    comment = client.post(
        f"/v1/posts/{post['id']}/comments", headers=USER_HEADERS, json={"body": "original"}
    ).json()
    assert comment["viewer_is_author"] is True

    forbidden_comment = client.patch(
        f"/v1/comments/{comment['id']}", headers=USER_2_HEADERS, json={"body": "hijack"}
    )
    assert forbidden_comment.status_code == 403

    edited_comment = client.patch(
        f"/v1/comments/{comment['id']}", headers=USER_HEADERS, json={"body": "fixed typo"}
    )
    assert edited_comment.status_code == 200
    assert edited_comment.json()["body"] == "fixed typo"
    assert edited_comment.json()["edited_at"] is not None

    # Viewer-is-author flags surface in reads with the viewer header.
    read = client.get(f"/v1/posts/{post['id']}", headers=USER_2_HEADERS).json()
    assert read["viewer_is_author"] is False
    comments = client.get(f"/v1/posts/{post['id']}/comments", headers=USER_HEADERS).json()
    assert comments[0]["viewer_is_author"] is True


def test_owner_can_delete_comment_with_thread(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)

    top = client.post(
        f"/v1/posts/{post['id']}/comments", headers=USER_HEADERS, json={"body": "top"}
    ).json()
    client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_2_HEADERS,
        json={"body": "reply", "parent_id": top["id"]},
    )

    # Only the author may delete; replies go with the thread (FK cascade).
    forbidden = client.delete(f"/v1/comments/{top['id']}", headers=USER_2_HEADERS)
    assert forbidden.status_code == 403

    deleted = client.delete(f"/v1/comments/{top['id']}", headers=USER_HEADERS)
    assert deleted.status_code == 204

    remaining = client.get(f"/v1/posts/{post['id']}/comments", headers=TOKEN_HEADERS).json()
    assert remaining == []
    assert client.get(f"/v1/posts/{post['id']}", headers=TOKEN_HEADERS).json()["comment_count"] == 0


def test_owner_can_delete_post_with_interactions(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)

    client.post(f"/v1/posts/{post['id']}/comments", headers=USER_2_HEADERS, json={"body": "hi"})
    client.put(f"/v1/posts/{post['id']}/reaction", headers=USER_2_HEADERS, json={"kind": "up"})
    client.put(f"/v1/posts/{post['id']}/emoji", headers=USER_2_HEADERS, json={"emoji": "🔥"})

    forbidden = client.delete(f"/v1/posts/{post['id']}", headers=USER_2_HEADERS)
    assert forbidden.status_code == 403

    deleted = client.delete(f"/v1/posts/{post['id']}", headers=USER_HEADERS)
    assert deleted.status_code == 204
    assert client.get(f"/v1/posts/{post['id']}", headers=TOKEN_HEADERS).status_code == 404


def test_hidden_posts_reject_comments_votes_and_emoji(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)
    comment = client.post(
        f"/v1/posts/{post['id']}/comments", headers=USER_2_HEADERS, json={"body": "hi"}
    ).json()
    row = session.get(Post, post["id"])
    assert row is not None
    row.hidden_at = utc_now()
    session.commit()

    assert client.get(f"/v1/posts/{post['id']}/comments", headers=TOKEN_HEADERS).status_code == 404
    assert (
        client.put(f"/v1/posts/{post['id']}/reaction", headers=USER_HEADERS, json={"kind": "up"})
        .status_code
        == 404
    )
    assert (
        client.put(
            f"/v1/comments/{comment['id']}/reaction",
            headers=USER_HEADERS,
            json={"kind": "up"},
        ).status_code
        == 404
    )
    assert (
        client.put(f"/v1/posts/{post['id']}/emoji", headers=USER_HEADERS, json={"emoji": "🔥"})
        .status_code
        == 404
    )


def test_reports_for_post_and_comment_are_visible_to_content_owner(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)
    comment = client.post(
        f"/v1/posts/{post['id']}/comments", headers=USER_HEADERS, json={"body": "bad reply"}
    ).json()

    post_report = client.post(
        "/v1/reports",
        headers=USER_2_HEADERS,
        json={"target_type": "post", "target_id": post["id"], "reason": "spam", "note": "bot"},
    )
    comment_report = client.post(
        "/v1/reports",
        headers=USER_2_HEADERS,
        json={"target_type": "comment", "target_id": comment["id"], "reason": "harassment"},
    )

    assert post_report.status_code == 201
    assert comment_report.status_code == 201
    assert "reporter_user_id" not in post_report.json()
    reports = client.get("/v1/moderation/reports", headers=USER_HEADERS)
    assert reports.status_code == 200
    assert {report["id"] for report in reports.json()} == {
        post_report.json()["id"],
        comment_report.json()["id"],
    }
    stored_report = session.scalar(
        select(SafetyReport).where(SafetyReport.id == post_report.json()["id"])
    )
    assert stored_report is not None


def test_blocked_user_cannot_comment_or_mention_blocker(session: Session) -> None:
    client = TestClient(app)
    post = _create_post(client)
    block = client.post(
        "/v1/blocks/user-2", headers=USER_HEADERS, json={"blocked_username": "replyguy"}
    )
    assert block.status_code == 200

    comment = client.post(
        f"/v1/posts/{post['id']}/comments", headers=USER_2_HEADERS, json={"body": "blocked"}
    )
    mention = client.post(
        "/v1/posts",
        headers=USER_2_HEADERS,
        json={
            "body": "mention",
            "mentions": [{"mention_type": "user", "target_handle": "nightcrawler"}],
        },
    )

    assert comment.status_code == 403
    assert mention.status_code == 403


def test_blocked_user_cannot_add_blocker_mention_by_edit(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _resolve(_settings: object, handle: str) -> dict[str, str | None] | None:
        if handle == "nightcrawler":
            return {
                "mention_type": "user",
                "target_handle": "nightcrawler",
                "target_id": "user-1",
                "display_name": "Night Crawler",
                "target_url": "/u/nightcrawler",
                "recipient_user_id": "user-1",
            }
        return None

    monkeypatch.setattr(routes, "resolve_profile_or_page_mention", _resolve)
    client = TestClient(app)
    assert (
        client.post("/v1/blocks/user-2", headers=USER_HEADERS, json={"blocked_username": "warper"})
        .status_code
        == 200
    )
    blocked_post = client.post(
        "/v1/posts", headers=USER_2_HEADERS, json={"body": "plain post"}
    ).json()
    blocked_comment = client.post(
        f"/v1/posts/{blocked_post['id']}/comments",
        headers=USER_2_HEADERS,
        json={"body": "plain comment"},
    ).json()

    edit_post = client.patch(
        f"/v1/posts/{blocked_post['id']}",
        headers=USER_2_HEADERS,
        json={"body": "hello @nightcrawler"},
    )
    edit_comment = client.patch(
        f"/v1/comments/{blocked_comment['id']}",
        headers=USER_2_HEADERS,
        json={"body": "hello @nightcrawler"},
    )

    assert edit_post.status_code == 403
    assert edit_comment.status_code == 403


def test_safety_audit_log_records_blocks_reports_and_moderation_decisions(
    session: Session,
) -> None:
    client = TestClient(app)
    post = _create_post(client)

    block = client.post(
        "/v1/blocks/user-2", headers=USER_HEADERS, json={"blocked_username": "warper"}
    )
    report = client.post(
        "/v1/reports",
        headers=USER_2_HEADERS,
        json={
            "target_type": "post",
            "target_id": post["id"],
            "reason": "harassment",
            "note": "contains secret_location=backroom token=abc",
        },
    )
    decision = client.patch(
        f"/v1/moderation/reports/{report.json()['id']}",
        headers=USER_HEADERS,
        json={"status": "resolved", "action": "hide", "note": "handled token=secret"},
    )

    assert block.status_code == 200
    assert report.status_code == 201
    assert decision.status_code == 200
    entries = session.scalars(
        select(SafetyAuditLog).order_by(SafetyAuditLog.created_at, SafetyAuditLog.action)
    ).all()
    assert [entry.action for entry in entries] == [
        "user.blocked",
        "report.created",
        "moderation.hide",
        "report.resolved",
    ]
    assert {entry.actor_user_id for entry in entries} == {"user-1", "user-2"}
    assert all("token" not in str(entry.metadata_json) for entry in entries)
    assert all("secret_location" not in str(entry.metadata_json) for entry in entries)

    audit_response = client.get("/v1/safety/audit-log", headers=USER_HEADERS)
    assert audit_response.status_code == 200
    assert [entry["action"] for entry in audit_response.json()] == [
        "user.blocked",
        "moderation.hide",
        "report.resolved",
    ]


def test_write_rate_limit(session: Session) -> None:
    from social.main_dependencies import settings

    settings.write_rate_limit_count = 1
    client = TestClient(app)

    first_write = client.post("/v1/posts", headers=USER_HEADERS, json={"body": "allowed"})
    second_write = client.post("/v1/posts", headers=USER_HEADERS, json={"body": "blocked"})

    assert first_write.status_code == 201
    assert second_write.status_code == 429


def test_comment_fanout_requests_notification(session: Session, monkeypatch: object) -> None:
    client = TestClient(app)
    calls: list[dict[str, object]] = []

    async def fake_create_notification(_settings: object, **payload: object) -> None:
        calls.append(payload)

    monkeypatch.setattr("social.api.routes.create_notification", fake_create_notification)

    post = client.post("/v1/posts", headers=USER_HEADERS, json={"body": "notify me"}).json()
    response = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_2_HEADERS,
        json={"body": "comment body"},
    )

    assert response.status_code == 201
    assert calls == [
        {
            "recipient_user_id": "user-1",
            "actor_user_id": "user-2",
            "event_type": "comment.created",
            "target_type": "post",
            "target_id": post["id"],
            "target_url": f"/posts/{post['id']}",
            "title": "warper commented on your post",
            "dedupe_key": f"comment:{post['id']}:user-2:user-1",
            "metadata": {
                "post_id": post["id"],
                "comment_id": response.json()["id"],
                "actor_username": "warper",
                "actor_display_name": "Warper",
            },
        }
    ]
