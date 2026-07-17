from datetime import UTC, datetime
from typing import Any

import pytest
from events.api import routes
from events.domain.models import (
    CheckInStatus,
    Event,
    EventAccessAuditLog,
    EventBoost,
    EventCheckInToken,
    EventFollow,
    EventGuestlistEntry,
    EventGuestQuota,
    GuestlistEntryStatus,
)
from events.main import app
from events.main_dependencies import settings
from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import select, update
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from events import users_client

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
PAGE_ID = "00000000-0000-0000-0000-000000000001"

EVENT_PAYLOAD = {
    "title": "Bass Theory",
    "slug": "bass-theory",
    "starts_at": "2026-08-15T20:00:00Z",
    "city": "Berlin",
    "page_id": PAGE_ID,
    "genres": ["dnb", "bass"],
    "description": "A deep dive into low frequencies.",
    "venue_name": "Berghain",
    "address": "Am Wriezener Bahnhof, Berlin",
    "lineup": [{"name": "DJ Sub"}],
}


def test_healthz() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "events"}


def test_readyz_checks_database(session: Session) -> None:
    client = TestClient(app)
    response = client.get("/readyz")
    assert response.status_code == 200


def test_create_event_happy_path(session: Session) -> None:
    client = TestClient(app)
    response = client.post("/v1/events", headers=USER_HEADERS, json=EVENT_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "bass-theory"
    assert body["title"] == "Bass Theory"
    assert body["city"] == "Berlin"
    assert body["location_mode"] == "public_location"
    assert body["genres"] == ["dnb", "bass"]
    assert body["page_id"] == PAGE_ID
    assert body["created_by_user_id"] == "user-1"
    assert body["boost_count"] == 0
    assert body["follower_count"] == 0
    assert body["is_following"] is False
    assert body["is_boosting"] is False


def test_create_event_crossposts_once_to_official_city_group(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    announcements: list[dict[str, str]] = []

    def _announce_event_city_group(_settings: object, event: Event) -> bool:
        announcements.append(
            {
                "event_id": event.id,
                "event_slug": event.slug,
                "event_title": event.title,
                "city": event.city,
                "page_id": event.page_id,
                "actor_user_id": event.created_by_user_id,
            }
        )
        return True

    monkeypatch.setattr(routes, "_announce_event_city_group", _announce_event_city_group)

    create_response = client.post("/v1/events", headers=USER_HEADERS, json=EVENT_PAYLOAD)
    update_response = client.patch(
        "/v1/events/bass-theory", headers=USER_HEADERS, json={"title": "Bass Theory Edit"}
    )
    organizer_update_response = client.post(
        "/v1/events/bass-theory/updates",
        headers=USER_HEADERS,
        json={"body": "No city group spam on organizer updates."},
    )

    assert create_response.status_code == 201
    assert update_response.status_code == 200
    assert organizer_update_response.status_code == 201
    assert announcements == [
        {
            "event_id": create_response.json()["id"],
            "event_slug": "bass-theory",
            "event_title": "Bass Theory",
            "city": "Berlin",
            "page_id": PAGE_ID,
            "actor_user_id": "user-1",
        }
    ]


def test_create_event_succeeds_when_city_crosspost_has_no_group(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _missing_group(_settings: object, _event: Event) -> bool:
        return False

    monkeypatch.setattr(routes, "_announce_event_city_group", _missing_group)
    response = TestClient(app).post("/v1/events", headers=USER_HEADERS, json=EVENT_PAYLOAD)

    assert response.status_code == 201
    assert response.json()["slug"] == "bass-theory"


def test_create_event_accepts_linked_artist_lineup_and_filters_by_artist(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)

    def _get_artist_ref(_settings: object, artist_user_id: str) -> dict[str, str] | None:
        if artist_user_id != "artist-user-1":
            return None
        return {
            "artist_profile_id": "artist-user-1",
            "username": "djlinked",
            "display_name": "DJ Linked",
            "target_url": "/u/djlinked",
        }

    monkeypatch.setattr(users_client, "get_artist_ref", _get_artist_ref)
    monkeypatch.setattr(
        users_client,
        "get_artist_refs",
        lambda settings, ids: {
            artist_id: ref
            for artist_id in ids
            if (ref := _get_artist_ref(settings, artist_id)) is not None
        },
    )
    response = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "linked-lineup",
            "lineup": [{"name": "DJ Linked", "artist_profile_id": "artist-user-1"}],
        },
    )

    assert response.status_code == 201
    assert response.json()["lineup"] == [
        {
            "name": "DJ Linked",
            "artist_profile_id": "artist-user-1",
            "artist_handle": "djlinked",
            "display_name": "DJ Linked",
            "target_url": "/u/djlinked",
        }
    ]

    listed = client.get(
        "/v1/events?lineup_artist_user_id=artist-user-1", headers=TOKEN_HEADERS
    )
    assert listed.status_code == 200
    assert [event["slug"] for event in listed.json()["items"]] == ["linked-lineup"]


def test_create_event_rejects_unknown_lineup_artist(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    batch_calls: list[list[str]] = []
    single_calls: list[str] = []
    monkeypatch.setattr(
        users_client,
        "get_artist_refs",
        lambda _settings, ids: batch_calls.append(ids) or {},
    )
    monkeypatch.setattr(
        users_client,
        "get_artist_ref",
        lambda _settings, artist_id: single_calls.append(artist_id),
    )

    response = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "bad-lineup",
            "lineup": [{"name": "Ghost", "artist_profile_id": "missing-artist"}],
        },
    )

    assert response.status_code == 422
    assert batch_calls == [["missing-artist"]]
    assert single_calls == []


def test_create_and_update_event_batch_validate_100_linked_lineup_entries(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    batch_calls: list[list[str]] = []
    single_calls: list[str] = []

    def get_artist_refs(
        _settings: object, artist_ids: list[str]
    ) -> dict[str, dict[str, str]]:
        batch_calls.append(artist_ids)
        return {
            artist_id: {
                "artist_profile_id": artist_id,
                "user_id": f"user-{artist_id}",
                "owner_user_id": f"user-{artist_id}",
                "username": artist_id,
                "display_name": artist_id,
                "target_url": f"/u/{artist_id}",
            }
            for artist_id in artist_ids
        }

    monkeypatch.setattr(users_client, "get_artist_refs", get_artist_refs)
    monkeypatch.setattr(
        users_client,
        "get_artist_ref",
        lambda _settings, artist_id: single_calls.append(artist_id),
    )
    name_only = [{"name": "Unlinked Artist"}]
    name_only_response = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={**EVENT_PAYLOAD, "slug": "name-only-lineup", "lineup": name_only},
    )
    assert name_only_response.status_code == 201
    assert name_only_response.json()["lineup"] == name_only
    assert batch_calls == []
    assert single_calls == []

    create_ids = [f"artist-{index}" for index in range(99)] + ["artist-0"]
    create_lineup = [
        {"name": f"Artist {index}", "artist_profile_id": artist_id}
        for index, artist_id in enumerate(create_ids)
    ]
    accepted_create = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={**EVENT_PAYLOAD, "slug": "lineup-boundary", "lineup": create_lineup},
    )
    assert accepted_create.status_code == 201
    assert batch_calls == [[f"artist-{index}" for index in range(99)]]
    assert single_calls == []

    batch_calls.clear()
    rejected_create = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "lineup-too-large",
            "lineup": [*create_lineup, {"name": "101", "artist_profile_id": "artist-100"}],
        },
    )
    assert rejected_create.status_code == 422
    assert batch_calls == []
    assert single_calls == []

    update_ids = [f"artist-{index}" for index in range(100)]
    update_lineup = [
        {"name": f"Artist {index}", "artist_profile_id": artist_id}
        for index, artist_id in enumerate(update_ids)
    ]
    accepted_update = client.patch(
        "/v1/events/warehouse-signal",
        headers=USER_HEADERS,
        json={"lineup": update_lineup},
    )
    assert accepted_update.status_code == 200
    assert batch_calls == [update_ids]
    assert single_calls == []

    batch_calls.clear()
    rejected_update = client.patch(
        "/v1/events/warehouse-signal",
        headers=USER_HEADERS,
        json={"lineup": [*update_lineup, {"name": "101", "artist_profile_id": "artist-100"}]},
    )

    assert rejected_update.status_code == 422
    assert batch_calls == []
    assert single_calls == []


def test_list_events_can_sort_feed_candidates_by_publication_time(session: Session) -> None:
    client = TestClient(app)
    older_newer_start = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={**EVENT_PAYLOAD, "slug": "older-newer-start", "starts_at": "2026-09-20T20:00:00Z"},
    )
    assert older_newer_start.status_code == 201

    newer_older_start = Event(
        title="Newer publication",
        slug="newer-older-start",
        starts_at=datetime(2026, 8, 1, 20, tzinfo=UTC),
        city="Berlin",
        page_id=PAGE_ID,
        genres=[],
        description="Published after the other event but starts earlier.",
        venue_name="Room 2",
        address=None,
        lineup=[],
        created_by_user_id="user-1",
    )
    session.add(newer_older_start)
    session.commit()

    response = client.get("/v1/events?sort=created&limit=2", headers=USER_HEADERS)

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["items"]] == [
        "newer-older-start",
        "older-newer-start",
    ]


def test_list_events_upcoming_excludes_past_and_sorts_start_ascending(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    for slug, starts_at in [
        ("past-event", "2026-07-09T20:00:00Z"),
        ("next-event", "2026-07-11T20:00:00Z"),
        ("later-event", "2026-07-12T20:00:00Z"),
    ]:
        assert client.post(
            "/v1/events",
            headers=USER_HEADERS,
            json={**EVENT_PAYLOAD, "slug": slug, "starts_at": starts_at},
        ).status_code == 201
    monkeypatch.setattr(routes, "utc_now", lambda: datetime(2026, 7, 10, tzinfo=UTC))

    response = client.get("/v1/events?upcoming=true&limit=2", headers=USER_HEADERS)

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["items"]] == ["next-event", "later-event"]
    assert response.json()["next_before"] is None


def test_page_editor_can_create_public_event_update_and_notify_followers(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    notifications: list[dict[str, object]] = []

    def _notify_user(_settings: object, **payload: object) -> bool:
        notifications.append(payload)
        return True

    monkeypatch.setattr(users_client, "notify_user", _notify_user)
    follow = client.post("/v1/events/warehouse-signal/follow", headers=USER_2_HEADERS)
    assert follow.status_code == 200

    response = client.post(
        "/v1/events/warehouse-signal/updates",
        headers=USER_HEADERS,
        json={"body": "Doors open at 22:00. Bring ID."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["event_slug"] == "warehouse-signal"
    assert body["body"] == "Doors open at 22:00. Bring ID."
    assert body["author_user_id"] == "user-1"
    assert body["event_title"] == "Warehouse Signal"
    assert notifications == [
        {
            "recipient_user_id": "user-2",
            "actor_user_id": "user-1",
            "event_type": "event.post.created",
            "target_type": "event_update",
            "target_id": body["id"],
            "target_url": "/events/warehouse-signal",
            "title": "Warehouse Signal update",
            "body": "Doors open at 22:00. Bring ID.",
            "dedupe_key": f"event.post.created:{body['id']}:user-2",
            "metadata": {
                "event_id": body["event_id"],
                "event_slug": "warehouse-signal",
                "event_title": "Warehouse Signal",
                "event_update_id": body["id"],
            },
        }
    ]

    list_response = client.get("/v1/events/warehouse-signal/updates", headers=TOKEN_HEADERS)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["items"]] == [body["id"]]


def test_event_update_writes_require_page_role_and_safe_body(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)

    def _no_role(_settings: object, _page_id: str, _user_id: str) -> str | None:
        return None

    monkeypatch.setattr(users_client, "check_page_role", _no_role)
    forbidden = client.post(
        "/v1/events/warehouse-signal/updates",
        headers=USER_HEADERS,
        json={"body": "valid update"},
    )
    assert forbidden.status_code == 403

    monkeypatch.setattr(users_client, "check_page_role", lambda *_args: "admin")
    blank = client.post(
        "/v1/events/warehouse-signal/updates",
        headers=USER_HEADERS,
        json={"body": "   "},
    )
    html = client.post(
        "/v1/events/warehouse-signal/updates",
        headers=USER_HEADERS,
        json={"body": "<b>secret?</b>"},
    )
    assert blank.status_code == 422
    assert html.status_code == 422


def test_internal_mention_target_resolves_event(session: Session) -> None:
    client = TestClient(app)
    assert client.post("/v1/events", headers=USER_HEADERS, json=EVENT_PAYLOAD).status_code == 201

    response = client.get("/internal/v1/mention-targets/events/bass-theory", headers=TOKEN_HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "target_type": "event",
        "target_id": response.json()["target_id"],
        "handle": "bass-theory",
        "display_name": "Bass Theory",
        "target_url": "/events/bass-theory",
    }


def test_internal_mention_target_missing_event_returns_404(session: Session) -> None:
    client = TestClient(app)

    response = client.get(
        "/internal/v1/mention-targets/events/missing-event", headers=TOKEN_HEADERS
    )

    assert response.status_code == 404


def test_event_batch_requires_internal_token(session: Session) -> None:
    response = TestClient(app).post("/internal/v1/events/batch", json={"slugs": []})

    assert response.status_code == 401


def test_event_batch_empty_input_returns_empty(session: Session) -> None:
    response = TestClient(app).post(
        "/internal/v1/events/batch",
        headers=TOKEN_HEADERS,
        json={"slugs": []},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_event_batch_strictly_validates_request_and_limit(session: Session) -> None:
    client = TestClient(app)
    accepted = client.post(
        "/internal/v1/events/batch",
        headers=TOKEN_HEADERS,
        json={"slugs": ["warehouse-signal"] * 100},
    )
    too_many = client.post(
        "/internal/v1/events/batch",
        headers=TOKEN_HEADERS,
        json={"slugs": ["warehouse-signal"] * 101},
    )
    malformed = client.post(
        "/internal/v1/events/batch",
        headers=TOKEN_HEADERS,
        json={"slugs": ["Warehouse Signal"]},
    )
    extra = client.post(
        "/internal/v1/events/batch",
        headers=TOKEN_HEADERS,
        json={"slugs": [], "include_deleted": True},
    )

    assert accepted.status_code == 200
    assert too_many.status_code == 422
    assert malformed.status_code == 422
    assert extra.status_code == 422


def test_event_batch_preserves_order_with_one_query_and_no_artist_lookups(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artist_calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        users_client,
        "get_artist_ref",
        lambda _settings, artist_id: artist_calls.append(("single", artist_id)),
    )
    monkeypatch.setattr(
        users_client,
        "get_artist_refs",
        lambda _settings, artist_ids: artist_calls.append(("batch", artist_ids)),
    )
    lineup = [
        {
            "name": "DJ Sub",
            "artist_profile_id": "artist-1",
            "artist_handle": "djsub",
            "display_name": "DJ Sub",
            "target_url": "/u/djsub",
        },
        {
            "name": "MC Bass",
            "artist_profile_id": "artist-2",
            "artist_handle": "mcbass",
            "display_name": "MC Bass",
            "target_url": "/u/mcbass",
        },
    ]
    second = Event(
        slug="bass-theory",
        title="Bass Theory",
        starts_at=datetime(2026, 8, 15, 20, 0, tzinfo=UTC),
        city="Berlin",
        page_id=PAGE_ID,
        created_by_user_id="user-1",
        genres=["dnb", "bass"],
        venue_name="Berghain",
        address="Am Wriezener Bahnhof, Berlin",
        lineup=lineup,
        poster_media_asset_id="poster-1",
    )
    session.add(second)
    session.flush()
    session.add_all(
        [
            EventFollow(event_id=second.id, user_id="user-2"),
            EventBoost(event_id=second.id, user_id="user-3"),
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
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_select)
    try:
        response = TestClient(app).post(
            "/internal/v1/events/batch",
            headers=TOKEN_HEADERS,
            json={
                "slugs": [
                    "bass-theory",
                    "missing-event",
                    "warehouse-signal",
                    "bass-theory",
                ]
            },
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()] == [
        "bass-theory",
        "warehouse-signal",
    ]
    event_body = response.json()[0]
    assert event_body["page_id"] == PAGE_ID
    assert event_body["genres"] == ["dnb", "bass"]
    assert event_body["venue_name"] == "Berghain"
    assert event_body["address"] == "Am Wriezener Bahnhof, Berlin"
    assert event_body["lineup"] == lineup
    assert event_body["poster_media_asset_id"] == "poster-1"
    assert event_body["follower_count"] == 1
    assert event_body["boost_count"] == 1
    assert event_body["is_following"] is None
    assert event_body["is_boosting"] is None
    assert artist_calls == []
    assert len(selects) == 1


def test_event_batch_redacts_secret_location(session: Session) -> None:
    session.add(
        Event(
            slug="legacy-secret",
            title="Legacy Secret",
            starts_at=datetime(2026, 8, 15, 20, 0, tzinfo=UTC),
            city="Berlin",
            page_id=PAGE_ID,
            created_by_user_id="user-1",
            location_mode="secret_location",
            venue_name="Hidden Room",
            address="Secret Street 1",
        )
    )
    session.commit()

    response = TestClient(app).post(
        "/internal/v1/events/batch",
        headers=TOKEN_HEADERS,
        json={"slugs": ["legacy-secret"]},
    )

    assert response.status_code == 200
    assert response.json()[0]["location_mode"] == "secret_location"
    assert response.json()[0]["venue_name"] is None
    assert response.json()[0]["address"] is None


@pytest.mark.parametrize(
    "slug",
    ["Has Uppercase", "with spaces", "special!chars", "üñïçödé", "ab"],
)
def test_create_event_invalid_slug(session: Session, slug: str) -> None:
    client = TestClient(app)
    payload = {**EVENT_PAYLOAD, "slug": slug}
    response = client.post("/v1/events", headers=USER_HEADERS, json=payload)
    assert response.status_code == 422


def test_create_event_duplicate_slug(session: Session) -> None:
    client = TestClient(app)
    first = client.post("/v1/events", headers=USER_HEADERS, json=EVENT_PAYLOAD)
    assert first.status_code == 201
    second = client.post("/v1/events", headers=USER_HEADERS, json=EVENT_PAYLOAD)
    assert second.status_code == 409


def test_create_event_legacy_public_input_emits_public_location(session: Session) -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={**EVENT_PAYLOAD, "slug": "legacy-public", "location_mode": "public"},
    )

    assert response.status_code == 201
    assert response.json()["location_mode"] == "public_location"


def test_create_event_tba_location_mode(session: Session) -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "location-tba",
            "location_mode": "tba",
            "venue_name": None,
            "address": None,
        },
    )

    assert response.status_code == 201
    assert response.json()["location_mode"] == "tba"


def test_create_and_update_secret_location_rejected(session: Session) -> None:
    client = TestClient(app)
    create_response = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={**EVENT_PAYLOAD, "slug": "secret-party", "location_mode": "secret_location"},
    )
    update_response = client.patch(
        "/v1/events/warehouse-signal",
        headers=USER_HEADERS,
        json={"location_mode": "secret_location"},
    )

    assert create_response.status_code == 422
    assert update_response.status_code == 422


def test_legacy_secret_location_row_redacts_exact_location(session: Session) -> None:
    session.add(
        Event(
            slug="legacy-secret",
            title="Legacy Secret",
            starts_at=datetime(2026, 8, 15, 20, 0, tzinfo=UTC),
            city="Berlin",
            page_id=PAGE_ID,
            created_by_user_id="user-1",
            location_mode="secret_location",
            venue_name="Hidden Room",
            address="Secret Street 1",
        )
    )
    session.commit()

    response = TestClient(app).get("/v1/events/legacy-secret", headers=TOKEN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["location_mode"] == "secret_location"
    assert body["venue_name"] is None
    assert body["address"] is None


def test_create_event_without_page_role(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_role(_settings: object, _page_id: str, _user_id: str) -> str | None:
        return None

    monkeypatch.setattr(users_client, "check_page_role", _no_role)
    client = TestClient(app)
    response = client.post("/v1/events", headers=USER_HEADERS, json=EVENT_PAYLOAD)
    assert response.status_code == 403


def test_create_event_validates_poster_media_asset(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from events import media_client

    seen: dict[str, object] = {}

    def _validate_event_poster_asset(
        settings_obj: object, *, asset_id: str, owner_user_id: str
    ) -> None:
        seen.update(settings=settings_obj, asset_id=asset_id, owner_user_id=owner_user_id)

    monkeypatch.setattr(media_client, "validate_event_poster_asset", _validate_event_poster_asset)
    response = TestClient(app).post(
        "/v1/events",
        headers=USER_HEADERS,
        json={**EVENT_PAYLOAD, "slug": "with-poster", "poster_media_asset_id": "asset-poster-1"},
    )

    assert response.status_code == 201
    assert response.json()["poster_media_asset_id"] == "asset-poster-1"
    assert seen == {
        "settings": settings,
        "asset_id": "asset-poster-1",
        "owner_user_id": "user-1",
    }


def test_create_event_rejects_invalid_poster_media_asset_without_persisting(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from events import media_client

    def _invalid_asset(*_args: object, **_kwargs: object) -> None:
        raise media_client.MediaAssetValidationError("media asset owner mismatch")

    monkeypatch.setattr(media_client, "validate_event_poster_asset", _invalid_asset)
    response = TestClient(app).post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "bad-poster",
            "poster_media_asset_id": "asset-owned-by-other",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid poster media asset"
    assert session.query(Event).filter_by(slug="bad-poster").one_or_none() is None


def test_create_event_fails_closed_when_media_validation_is_not_configured(
    session: Session,
) -> None:
    response = TestClient(app).post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "unconfigured-poster",
            "poster_media_asset_id": "asset-poster-1",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid poster media asset"
    assert session.query(Event).filter_by(slug="unconfigured-poster").one_or_none() is None


def test_update_event_rejects_invalid_poster_media_asset_without_changing_event(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from events import media_client

    def _invalid_asset(*_args: object, **_kwargs: object) -> None:
        raise media_client.MediaAssetValidationError("media asset is not ready")

    monkeypatch.setattr(media_client, "validate_event_poster_asset", _invalid_asset)
    response = TestClient(app).patch(
        "/v1/events/warehouse-signal",
        headers=USER_HEADERS,
        json={"poster_media_asset_id": "pending-poster"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid poster media asset"
    event = session.query(Event).filter_by(slug="warehouse-signal").one()
    assert event.poster_media_asset_id is None


def test_get_event_by_slug_public(session: Session) -> None:
    client = TestClient(app)
    response = client.get("/v1/events/warehouse-signal", headers=TOKEN_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "warehouse-signal"
    assert body["is_following"] is None
    assert body["is_boosting"] is None


def test_list_events_city_filter(session: Session) -> None:
    client = TestClient(app)
    client.post("/v1/events", headers=USER_HEADERS, json=EVENT_PAYLOAD)
    response = client.get("/v1/events?city=Berlin", headers=TOKEN_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["city"] == "Berlin"


def test_list_events_query_matches_public_search_signals(session: Session) -> None:
    client = TestClient(app)
    client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "ambient-ritual",
            "title": "Ambient Ritual",
            "city": "Poznan",
            "genres": ["ambient", "drone"],
            "venue_name": "Generator Hall",
            "lineup": [{"name": "Soft Circuit"}],
        },
    )

    by_genre = client.get("/v1/events?q=drone", headers=TOKEN_HEADERS)
    by_lineup = client.get("/v1/events?q=soft", headers=TOKEN_HEADERS)
    by_city = client.get("/v1/events?q=poznan", headers=TOKEN_HEADERS)
    by_venue = client.get("/v1/events?q=generator", headers=TOKEN_HEADERS)

    session.add(
        Event(
            title="Hidden Coordinates",
            slug="hidden-coordinates",
            starts_at=datetime(2026, 9, 7, 20, 0, tzinfo=UTC),
            city="Poznan",
            page_id=PAGE_ID,
            created_by_user_id="user-1",
            location_mode="secret_location",
            venue_name="Private Bunker",
            address="Secret Street 13",
        )
    )
    session.commit()
    by_secret_venue = client.get("/v1/events?q=bunker", headers=TOKEN_HEADERS)

    assert by_genre.status_code == 200
    assert [item["slug"] for item in by_genre.json()["items"]] == ["ambient-ritual"]
    assert [item["slug"] for item in by_lineup.json()["items"]] == ["ambient-ritual"]
    assert [item["slug"] for item in by_city.json()["items"]] == ["ambient-ritual"]
    assert [item["slug"] for item in by_venue.json()["items"]] == ["ambient-ritual"]
    assert by_secret_venue.json()["items"] == []


def test_list_events_can_filter_upcoming_by_linked_artist_profile_id(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    linked_artist_id = "11111111-1111-1111-1111-111111111111"
    other_artist_id = "22222222-2222-2222-2222-222222222222"

    def _get_artist_ref(_settings: object, artist_id: str) -> dict[str, str] | None:
        if artist_id == linked_artist_id:
            return {
                "artist_profile_id": artist_id,
                "username": "linkedartist",
                "display_name": "Linked Artist",
                "target_url": "/u/linkedartist",
            }
        return None

    monkeypatch.setattr(users_client, "get_artist_ref", _get_artist_ref)
    monkeypatch.setattr(
        users_client,
        "get_artist_refs",
        lambda settings, ids: {
            artist_id: ref
            for artist_id in ids
            if (ref := _get_artist_ref(settings, artist_id)) is not None
        },
    )
    client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "linked-lineup",
            "lineup": [{"artist_profile_id": linked_artist_id, "name": "Linked Artist"}],
        },
    )
    client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "fallback-lineup",
            "lineup": [{"name": "Fallback Only"}],
        },
    )

    response = client.get(
        f"/v1/events?artist_profile_id={linked_artist_id}", headers=TOKEN_HEADERS
    )
    empty = client.get(f"/v1/events?artist_profile_id={other_artist_id}", headers=TOKEN_HEADERS)

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()["items"]] == ["linked-lineup"]
    assert empty.status_code == 200
    assert empty.json()["items"] == []


def test_lineup_keeps_display_name_fallback_with_artist_profile_id(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    artist_profile_id = "11111111-1111-1111-1111-111111111111"

    def _get_artist_ref(_settings: object, artist_id: str) -> dict[str, str] | None:
        return {
            "artist_profile_id": artist_id,
            "username": "aliasartist",
            "display_name": "Canonical Artist",
            "target_url": "/u/aliasartist",
        }

    monkeypatch.setattr(users_client, "get_artist_ref", _get_artist_ref)
    monkeypatch.setattr(
        users_client,
        "get_artist_refs",
        lambda settings, ids: {
            artist_id: _get_artist_ref(settings, artist_id) for artist_id in ids
        },
    )

    response = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "stable-lineup-entry",
            "lineup": [{"artist_profile_id": artist_profile_id, "name": "Alias On Flyer"}],
        },
    )

    assert response.status_code == 201
    assert response.json()["lineup"] == [
        {
            "artist_profile_id": artist_profile_id,
            "name": "Alias On Flyer",
            "artist_handle": "aliasartist",
            "display_name": "Canonical Artist",
            "target_url": "/u/aliasartist",
        }
    ]


def test_list_events_page_id_filter(session: Session) -> None:
    client = TestClient(app)
    response = client.get(f"/v1/events?page_id={PAGE_ID}", headers=TOKEN_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["slug"] == "warehouse-signal"


def test_list_events_cursor_pagination(session: Session) -> None:
    client = TestClient(app)
    for i in range(3):
        client.post(
            "/v1/events",
            headers=USER_HEADERS,
            json={
                **EVENT_PAYLOAD,
                "slug": f"event-{i}",
                "starts_at": f"2026-0{i + 1}-15T20:00:00Z",
            },
        )
    first_page = client.get("/v1/events?limit=2", headers=TOKEN_HEADERS)
    assert first_page.status_code == 200
    body = first_page.json()
    assert len(body["items"]) == 2
    assert body["next_before"] is not None

    second_page = client.get(
        f"/v1/events?limit=2&before={body['next_before']}", headers=TOKEN_HEADERS
    )
    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) >= 1


def test_follow_and_unfollow(session: Session) -> None:
    client = TestClient(app)
    follow = client.post("/v1/events/warehouse-signal/follow", headers=USER_HEADERS)
    assert follow.status_code == 200
    assert follow.json()["is_following"] is True
    assert follow.json()["follower_count"] == 1

    unfollow = client.delete("/v1/events/warehouse-signal/follow", headers=USER_HEADERS)
    assert unfollow.status_code == 204

    after = client.get(
        "/v1/events/warehouse-signal", headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "user-1"}
    )
    assert after.json()["is_following"] is False
    assert after.json()["follower_count"] == 0


def test_duplicate_follow_409(session: Session) -> None:
    client = TestClient(app)
    first = client.post("/v1/events/warehouse-signal/follow", headers=USER_HEADERS)
    assert first.status_code == 200
    second = client.post("/v1/events/warehouse-signal/follow", headers=USER_HEADERS)
    assert second.status_code == 409


def test_boost_and_unboost(session: Session) -> None:
    client = TestClient(app)
    boost = client.post("/v1/events/warehouse-signal/boost", headers=USER_HEADERS)
    assert boost.status_code == 200
    assert boost.json()["is_boosting"] is True
    assert boost.json()["boost_count"] == 1

    unboost = client.delete("/v1/events/warehouse-signal/boost", headers=USER_HEADERS)
    assert unboost.status_code == 204

    after = client.get(
        "/v1/events/warehouse-signal", headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "user-1"}
    )
    assert after.json()["is_boosting"] is False
    assert after.json()["boost_count"] == 0


def test_duplicate_boost_409(session: Session) -> None:
    client = TestClient(app)
    first = client.post("/v1/events/warehouse-signal/boost", headers=USER_HEADERS)
    assert first.status_code == 200
    second = client.post("/v1/events/warehouse-signal/boost", headers=USER_HEADERS)
    assert second.status_code == 409


def test_counts_with_multiple_users(session: Session) -> None:
    client = TestClient(app)
    client.post("/v1/events/warehouse-signal/follow", headers=USER_HEADERS)
    client.post("/v1/events/warehouse-signal/follow", headers=USER_2_HEADERS)
    client.post("/v1/events/warehouse-signal/boost", headers=USER_HEADERS)

    body = client.get(
        "/v1/events/warehouse-signal", headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "user-1"}
    ).json()
    assert body["follower_count"] == 2
    assert body["boost_count"] == 1
    assert body["is_following"] is True
    assert body["is_boosting"] is True

    as_user2 = client.get(
        "/v1/events/warehouse-signal", headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "user-2"}
    ).json()
    assert as_user2["is_following"] is True
    assert as_user2["is_boosting"] is False


def test_is_following_none_when_unauthenticated(session: Session) -> None:
    client = TestClient(app)
    client.post("/v1/events/warehouse-signal/follow", headers=USER_HEADERS)
    body = client.get("/v1/events/warehouse-signal", headers=TOKEN_HEADERS).json()
    assert body["is_following"] is None
    assert body["is_boosting"] is None
    assert body["follower_count"] == 1


def test_update_event_partial(session: Session) -> None:
    client = TestClient(app)
    response = client.patch(
        "/v1/events/warehouse-signal",
        headers=USER_HEADERS,
        json={"title": "Updated Title", "city": "Wroclaw"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Updated Title"
    assert body["city"] == "Wroclaw"
    assert body["slug"] == "warehouse-signal"


def test_update_event_without_role(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_role(_settings: object, _page_id: str, _user_id: str) -> str | None:
        return None

    monkeypatch.setattr(users_client, "check_page_role", _no_role)
    client = TestClient(app)
    response = client.patch(
        "/v1/events/warehouse-signal",
        headers=USER_HEADERS,
        json={"title": "Hijacked"},
    )
    assert response.status_code == 403


def test_delete_event_soft(session: Session) -> None:
    client = TestClient(app)
    deleted = client.delete("/v1/events/warehouse-signal", headers=USER_HEADERS)
    assert deleted.status_code == 204

    not_found = client.get("/v1/events/warehouse-signal", headers=TOKEN_HEADERS)
    assert not_found.status_code == 404

    listed = client.get("/v1/events", headers=TOKEN_HEADERS).json()
    assert len(listed["items"]) == 0


def test_rate_limit(session: Session) -> None:
    settings.write_rate_limit_count = 1
    client = TestClient(app)
    first = client.post("/v1/events/warehouse-signal/follow", headers=USER_HEADERS)
    assert first.status_code == 200
    second = client.post("/v1/events/warehouse-signal/boost", headers=USER_HEADERS)
    assert second.status_code == 429


def test_organizer_manages_private_guestlist_and_notifies_guest(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    notifications: list[dict[str, object]] = []
    monkeypatch.setattr(
        users_client,
        "notify_user",
        lambda _settings, **payload: notifications.append(payload) or True,
    )

    response = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_HEADERS,
        json={"user_id": "guest-1", "username": "guestone", "display_name": "Guest One"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == "guest-1"
    assert body["status"] == "active"
    assert body["source"] == "organizer"
    assert notifications[0]["recipient_user_id"] == "guest-1"
    assert notifications[0]["event_type"] == "guestlist.added"
    assert "address" not in notifications[0]["metadata"]

    access = client.get(
        "/v1/events/warehouse-signal/access",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "guest-1"},
    )
    assert access.status_code == 200
    assert access.json()["can_check_in"] is True

    removed = client.delete(
        "/v1/events/warehouse-signal/guestlist/guest-1", headers=USER_HEADERS
    )
    assert removed.status_code == 204
    access_after_remove = client.get(
        "/v1/events/warehouse-signal/access",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "guest-1"},
    )
    assert access_after_remove.status_code == 404


def test_dj_guest_quota_enforced_by_linked_artist_owner(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    artist_profile_id = "11111111-1111-1111-1111-111111111111"

    def get_artist(_settings: object, artist_id: str) -> dict[str, str]:
        return {
            "artist_profile_id": artist_id,
            "username": "djquota",
            "display_name": "DJ Quota",
            "target_url": "/u/djquota",
            "owner_user_id": "dj-user-1",
        }

    monkeypatch.setattr(users_client, "get_artist_ref", get_artist)
    monkeypatch.setattr(
        users_client,
        "get_artist_refs",
        lambda settings, artist_ids: {
            artist_id: get_artist(settings, artist_id) for artist_id in artist_ids
        },
    )
    create = client.post(
        "/v1/events",
        headers=USER_HEADERS,
        json={
            **EVENT_PAYLOAD,
            "slug": "quota-night",
            "lineup": [{"name": "DJ Quota", "artist_profile_id": artist_profile_id}],
        },
    )
    assert create.status_code == 201
    quota = client.put(
        "/v1/events/quota-night/guest-quotas/11111111-1111-1111-1111-111111111111",
        headers=USER_HEADERS,
        json={"quota": 1},
    )
    assert quota.status_code == 200

    dj_headers = {**TOKEN_HEADERS, "X-Threshold-User-Id": "dj-user-1"}
    first = client.post(
        "/v1/events/quota-night/guestlist/dj",
        headers=dj_headers,
        json={"artist_profile_id": artist_profile_id, "user_id": "guest-1"},
    )
    second = client.post(
        "/v1/events/quota-night/guestlist/dj",
        headers=dj_headers,
        json={"artist_profile_id": artist_profile_id, "user_id": "guest-2"},
    )
    impostor = client.post(
        "/v1/events/quota-night/guestlist/dj",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "other-dj"},
        json={"artist_profile_id": artist_profile_id, "user_id": "guest-3"},
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert impostor.status_code == 403


def test_manager_cannot_assign_quota_to_unlisted_artist(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    artist_calls: list[str] = []
    monkeypatch.setattr(
        users_client,
        "get_artist_ref",
        lambda _settings, artist_id: artist_calls.append(artist_id),
    )

    response = TestClient(app).put(
        "/v1/events/warehouse-signal/guestlist/quotas/unlisted-artist",
        headers=USER_HEADERS,
        json={"quota": 2},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "artist is not in event lineup"
    assert artist_calls == []
    assert session.scalar(select(EventGuestQuota)) is None


def test_removed_lineup_artist_cannot_use_existing_quota(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    artist_profile_id = "removed-lineup-artist"
    event = session.scalar(select(Event).where(Event.slug == "warehouse-signal"))
    assert event is not None
    event.lineup = [{"name": "Removed Artist", "artist_profile_id": artist_profile_id}]
    session.commit()
    artist_calls: list[str] = []

    def get_artist(_settings: object, artist_id: str) -> dict[str, str]:
        artist_calls.append(artist_id)
        return {
            "artist_profile_id": artist_id,
            "owner_user_id": "artist-owner",
            "username": "removedartist",
            "display_name": "Removed Artist",
            "target_url": "/u/removedartist",
        }

    monkeypatch.setattr(users_client, "get_artist_ref", get_artist)
    client = TestClient(app)
    quota = client.put(
        f"/v1/events/warehouse-signal/guestlist/quotas/{artist_profile_id}",
        headers=USER_HEADERS,
        json={"quota": 2},
    )
    assert quota.status_code == 200
    artist_calls.clear()
    event.lineup = []
    session.commit()

    response = client.post(
        "/v1/events/warehouse-signal/guestlist/dj",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "artist-owner"},
        json={"artist_profile_id": artist_profile_id, "user_id": "guest-after-removal"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "artist is not in event lineup"
    assert artist_calls == []
    assert session.scalar(
        select(EventGuestlistEntry).where(
            EventGuestlistEntry.guest_user_id == "guest-after-removal"
        )
    ) is None


def test_check_in_token_is_opaque_short_lived_and_one_time(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    monkeypatch.setattr(users_client, "notify_user", lambda *_args, **_kwargs: True)
    add = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_HEADERS,
        json={"user_id": "guest-1", "username": "guestone", "display_name": "Guest One"},
    )
    assert add.status_code == 201
    token_response = client.post(
        "/v1/events/warehouse-signal/check-in-tokens",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "guest-1"},
    )

    assert token_response.status_code == 201
    token_body = token_response.json()
    token = token_body["token"]
    assert "guest-1" not in token
    assert "warehouse-signal" not in token
    assert token_body["expires_at"]

    replacement_response = client.post(
        "/v1/events/warehouse-signal/check-in-tokens",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "guest-1"},
    )
    assert replacement_response.status_code == 201
    old_token_row = session.scalars(
        select(EventCheckInToken).where(EventCheckInToken.status == CheckInStatus.revoked.value)
    ).first()
    assert old_token_row is not None
    token = replacement_response.json()["token"]

    validated = client.post(
        "/v1/events/warehouse-signal/check-ins/validate",
        headers=USER_HEADERS,
        json={"token": token},
    )
    replay = client.post(
        "/v1/events/warehouse-signal/check-ins/validate",
        headers=USER_HEADERS,
        json={"token": token},
    )

    assert validated.status_code == 200
    assert validated.json() == {
        "status": "checked_in",
        "username": "guestone",
        "display_name": "Guest One",
    }
    assert replay.status_code == 409
    mint_after_check_in = client.post(
        "/v1/events/warehouse-signal/check-in-tokens",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "guest-1"},
    )
    assert mint_after_check_in.status_code == 409


def test_remove_and_readd_keeps_old_check_in_token_revoked(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(users_client, "notify_user", lambda *_args, **_kwargs: True)
    client = TestClient(app)
    assert (
        client.post(
            "/v1/events/warehouse-signal/guestlist",
            headers=USER_HEADERS,
            json={"user_id": "readded-guest", "display_name": "Readded Guest"},
        ).status_code
        == 201
    )
    old_token = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "readded-guest"},
    ).json()["token"]
    token_row = session.scalar(select(EventCheckInToken))
    assert token_row is not None

    assert (
        client.delete(
            "/v1/events/warehouse-signal/guestlist/readded-guest", headers=USER_HEADERS
        ).status_code
        == 204
    )
    session.expire_all()
    assert session.get(EventCheckInToken, token_row.id).status == CheckInStatus.revoked.value

    assert (
        client.post(
            "/v1/events/warehouse-signal/guestlist",
            headers=USER_HEADERS,
            json={"user_id": "readded-guest", "display_name": "Readded Guest"},
        ).status_code
        == 201
    )
    session.expire_all()
    assert session.get(EventCheckInToken, token_row.id).status == CheckInStatus.revoked.value
    old_check = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=USER_HEADERS,
        json={"token": old_token},
    )
    new_token = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "readded-guest"},
    )
    new_check = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=USER_HEADERS,
        json={"token": new_token.json()["token"]},
    )

    assert old_check.status_code == 409
    assert new_token.status_code == 201
    assert new_check.status_code == 200


def test_check_in_claim_conditionally_updates_only_issued_token(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(users_client, "notify_user", lambda *_args, **_kwargs: True)
    client = TestClient(app)
    client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_HEADERS,
        json={"user_id": "atomic-guest", "display_name": "Atomic Guest"},
    )
    token = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "atomic-guest"},
    ).json()["token"]
    token_claim_updates: list[str] = []

    def capture_update(
        _connection: Connection,
        _cursor: object,
        statement: str,
        _parameters: Any,
        _context: object,
        _executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("UPDATE") and "used_at" in statement:
            token_claim_updates.append(statement)

    engine = session.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_update)
    try:
        first = client.post(
            "/v1/events/warehouse-signal/check-in",
            headers=USER_HEADERS,
            json={"token": token},
        )
        second = client.post(
            "/v1/events/warehouse-signal/check-in",
            headers=USER_HEADERS,
            json={"token": token},
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_update)

    assert first.status_code == 200
    assert second.status_code == 409
    assert len(token_claim_updates) == 1
    assert "event_check_in_tokens.status =" in token_claim_updates[0]


def test_check_in_atomic_claim_loser_stops_before_check_in_and_audit(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(users_client, "notify_user", lambda *_args, **_kwargs: True)
    client = TestClient(app)
    added = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_HEADERS,
        json={"user_id": "claim-loser", "display_name": "Claim Loser"},
    )
    token = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "claim-loser"},
    ).json()["token"]
    token_row = session.scalar(select(EventCheckInToken))
    assert token_row is not None
    audits_before = len(session.scalars(select(EventAccessAuditLog)).all())
    original_claim = routes._claim_check_in_token

    def lose_claim(db_session: Session, *, token_id: str, used_at: datetime) -> bool:
        db_session.connection().execute(
            update(EventCheckInToken)
            .where(EventCheckInToken.id == token_id)
            .values(status=CheckInStatus.used.value, used_at=used_at)
        )
        return original_claim(db_session, token_id=token_id, used_at=used_at)

    monkeypatch.setattr(routes, "_claim_check_in_token", lose_claim)
    response = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=USER_HEADERS,
        json={"token": token},
    )
    session.expire_all()
    entry = session.get(EventGuestlistEntry, added.json()["id"])

    assert response.status_code == 409
    assert response.json()["detail"] == "check-in token already used"
    assert entry is not None
    assert entry.checked_in_at is None
    assert entry.checked_in_by_user_id is None
    assert len(session.scalars(select(EventAccessAuditLog)).all()) == audits_before



def test_organizer_adds_guest_and_guest_mints_one_time_check_in_token(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    notifications: list[dict[str, object]] = []
    monkeypatch.setattr(
        users_client,
        "notify_user",
        lambda _settings, **payload: notifications.append(payload) or True,
    )

    added = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_HEADERS,
        json={"guest_user_id": "guest-1", "guest_display_name": "Guest One"},
    )
    token = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "guest-1"},
    )
    first_check = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=USER_HEADERS,
        json={"token": token.json()["token"]},
    )
    second_check = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=USER_HEADERS,
        json={"token": token.json()["token"]},
    )

    assert added.status_code == 201
    assert added.json()["status"] == "active"
    assert token.status_code == 201
    assert token.json()["token"]
    assert token.json()["expires_at"]
    assert first_check.status_code == 200
    assert first_check.json() == {
        "status": "checked_in",
        "username": None,
        "display_name": "Guest One",
    }
    assert second_check.status_code == 409
    assert [n["event_type"] for n in notifications] == ["guestlist.added"]


def test_dj_guest_quota_enforced_and_artist_owner_checked(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    artist_profile_id = "artist-profile-1"

    def _get_artist_ref(_settings: object, artist_id: str) -> dict[str, str] | None:
        if artist_id != artist_profile_id:
            return None
        return {
            "artist_profile_id": artist_profile_id,
            "user_id": "user-2",
            "username": "warper",
            "display_name": "Warper",
            "target_url": "/u/warper",
        }

    monkeypatch.setattr(users_client, "get_artist_ref", _get_artist_ref)
    event = session.scalar(select(Event).where(Event.slug == "warehouse-signal"))
    assert event is not None
    event.lineup = [{"name": "Warper", "artist_profile_id": artist_profile_id}]
    session.commit()
    quota = client.put(
        f"/v1/events/warehouse-signal/guestlist/quotas/{artist_profile_id}",
        headers=USER_HEADERS,
        json={"quota": 1},
    )
    first = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_2_HEADERS,
        json={
            "guest_user_id": "guest-dj-1",
            "guest_display_name": "DJ Guest 1",
            "artist_profile_id": artist_profile_id,
        },
    )
    same_guest = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_2_HEADERS,
        json={
            "guest_user_id": "guest-dj-1",
            "guest_display_name": "DJ Guest 1",
            "artist_profile_id": artist_profile_id,
        },
    )
    over_limit = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_2_HEADERS,
        json={
            "guest_user_id": "guest-dj-2",
            "guest_display_name": "DJ Guest 2",
            "artist_profile_id": artist_profile_id,
        },
    )
    wrong_artist = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_HEADERS,
        json={
            "guest_user_id": "guest-bad",
            "guest_display_name": "Bad Guest",
            "artist_profile_id": artist_profile_id,
        },
    )

    assert quota.status_code == 200
    assert quota.json()["quota"] == 1
    assert first.status_code == 201
    assert first.json()["added_by_artist_profile_id"] == artist_profile_id
    assert same_guest.status_code == 201
    assert over_limit.status_code == 409
    assert wrong_artist.status_code == 403


def test_removed_guest_cannot_mint_token_and_check_in_requires_page_role(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    add = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_HEADERS,
        json={"guest_user_id": "guest-removed", "guest_display_name": "Removed Guest"},
    )
    remove = client.delete(
        "/v1/events/warehouse-signal/guestlist/guest-removed",
        headers=USER_HEADERS,
    )
    token = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "guest-removed"},
    )

    assert add.status_code == 201
    assert remove.status_code == 204
    assert token.status_code == 404

    client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=USER_HEADERS,
        json={"guest_user_id": "guest-door", "guest_display_name": "Door Guest"},
    )
    active_token = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "guest-door"},
    )
    monkeypatch.setattr(users_client, "check_page_role", lambda *_args: None)
    forbidden = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=USER_HEADERS,
        json={"token": active_token.json()["token"]},
    )
    assert forbidden.status_code == 403


def test_viewer_context_and_guestlist_require_authenticated_user(session: Session) -> None:
    client = TestClient(app)

    assert client.get("/v1/events/warehouse-signal/viewer-context").status_code == 401
    assert (
        client.get(
            "/v1/events/warehouse-signal/viewer-context", headers=TOKEN_HEADERS
        ).status_code
        == 401
    )
    assert (
        client.get("/v1/events/warehouse-signal/guestlist", headers=TOKEN_HEADERS).status_code
        == 401
    )


def test_ordinary_viewer_has_no_privileged_event_capabilities(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(users_client, "check_page_role", lambda *_args: None)

    response = TestClient(app).get(
        "/v1/events/warehouse-signal/viewer-context",
        headers={**USER_2_HEADERS, "X-Threshold-Page-Role": "owner"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["active_guest_access"] is None
    assert body["can_mint_qr"] is False
    assert body["can_manage_guestlist"] is False
    assert body["can_set_dj_quota"] is False
    assert body["can_check_in"] is False
    assert body["can_post_update"] is False
    assert body["viewer_lineup_artists"] == []
    assert body["quota_summaries"] == []


def test_viewer_context_returns_only_active_guest_access(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = session.scalar(select(Event).where(Event.slug == "warehouse-signal"))
    assert event is not None
    session.add_all(
        [
            EventGuestlistEntry(
                event_id=event.id,
                guest_user_id="active-guest",
                guest_display_name="Active Guest",
                added_by_user_id="user-1",
            ),
            EventGuestlistEntry(
                event_id=event.id,
                guest_user_id="removed-guest",
                guest_display_name="Removed Guest",
                added_by_user_id="user-1",
                status=GuestlistEntryStatus.removed.value,
            ),
            EventGuestlistEntry(
                event_id=event.id,
                guest_user_id="checked-guest",
                guest_display_name="Checked Guest",
                added_by_user_id="user-1",
                checked_in_at=datetime(2026, 7, 1, 23, tzinfo=UTC),
            ),
        ]
    )
    session.commit()
    monkeypatch.setattr(users_client, "check_page_role", lambda *_args: None)
    client = TestClient(app)

    active = client.get(
        "/v1/events/warehouse-signal/viewer-context",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "active-guest"},
    )
    removed = client.get(
        "/v1/events/warehouse-signal/viewer-context",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "removed-guest"},
    )
    checked = client.get(
        "/v1/events/warehouse-signal/viewer-context",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "checked-guest"},
    )

    assert active.status_code == 200
    assert active.json()["active_guest_access"]["status"] == "active"
    assert active.json()["can_mint_qr"] is True
    assert removed.status_code == 200
    assert removed.json()["active_guest_access"] is None
    assert removed.json()["can_mint_qr"] is False
    assert checked.status_code == 200
    assert checked.json()["active_guest_access"]["checked_in_at"] is not None
    assert checked.json()["can_mint_qr"] is False


@pytest.mark.parametrize("role", ["owner", "admin", "editor"])
def test_event_manager_roles_receive_manager_capabilities(
    session: Session, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    monkeypatch.setattr(users_client, "check_page_role", lambda *_args: role)

    response = TestClient(app).get(
        "/v1/events/warehouse-signal/viewer-context", headers=USER_HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["can_manage_guestlist"] is True
    assert body["can_set_dj_quota"] is True
    assert body["can_check_in"] is True
    assert body["can_post_update"] is True


def test_lineup_owner_context_dedupes_lookups_and_batches_quota_counts(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = session.scalar(select(Event).where(Event.slug == "warehouse-signal"))
    assert event is not None
    artist_with_quota = "artist-with-quota"
    artist_without_quota = "artist-without-quota"
    event.lineup = [
        {"name": "Quota", "artist_profile_id": artist_with_quota},
        {"name": "Quota duplicate", "artist_profile_id": artist_with_quota},
        {"name": "No quota", "artist_profile_id": artist_without_quota},
    ]
    session.add_all(
        [
            EventGuestQuota(
                event_id=event.id,
                artist_profile_id=artist_with_quota,
                assigned_by_user_id="user-1",
                quota=2,
            ),
            EventGuestlistEntry(
                event_id=event.id,
                guest_user_id="artist-guest",
                guest_display_name="Artist Guest",
                added_by_user_id="artist-owner",
                added_by_artist_profile_id=artist_with_quota,
            ),
        ]
    )
    session.commit()
    role_calls: list[tuple[str, str]] = []
    artist_calls: list[list[str]] = []
    single_artist_calls: list[str] = []

    def check_role(_settings: object, page_id: str, user_id: str) -> None:
        role_calls.append((page_id, user_id))

    def get_artists(_settings: object, artist_ids: list[str]) -> dict[str, dict[str, str]]:
        artist_calls.append(artist_ids)
        return {
            artist_id: {
                "artist_profile_id": artist_id,
                "owner_user_id": "artist-owner",
                "username": artist_id,
                "display_name": artist_id,
                "target_url": f"/u/{artist_id}",
            }
            for artist_id in artist_ids
        }

    monkeypatch.setattr(users_client, "check_page_role", check_role)
    monkeypatch.setattr(users_client, "get_artist_refs", get_artists)
    monkeypatch.setattr(
        users_client,
        "get_artist_ref",
        lambda _settings, artist_id: single_artist_calls.append(artist_id),
    )
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
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_select)
    try:
        response = TestClient(app).get(
            "/v1/events/warehouse-signal/viewer-context",
            headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "artist-owner"},
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200
    body = response.json()
    assert [item["artist_profile_id"] for item in body["viewer_lineup_artists"]] == [
        artist_with_quota,
        artist_without_quota,
    ]
    assert body["viewer_lineup_artists"][0]["quota"]["used"] == 1
    assert body["viewer_lineup_artists"][0]["quota"]["remaining"] == 1
    assert body["viewer_lineup_artists"][1]["quota"] is None
    assert body["can_manage_guestlist"] is False
    assert body["quota_summaries"] == []
    assert role_calls == [(PAGE_ID, "artist-owner")]
    assert artist_calls == [[artist_with_quota, artist_without_quota]]
    assert single_artist_calls == []
    assert len(selects) == 3

    unrelated = TestClient(app).get(
        "/v1/events/warehouse-signal/viewer-context",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "unrelated-artist-owner"},
    )
    assert unrelated.status_code == 200
    assert unrelated.json()["viewer_lineup_artists"] == []


def test_manager_context_returns_batched_quota_summaries(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = session.scalar(select(Event).where(Event.slug == "warehouse-signal"))
    assert event is not None
    session.add_all(
        [
            EventGuestQuota(
                event_id=event.id,
                artist_profile_id="artist-b",
                assigned_by_user_id="user-1",
                quota=3,
            ),
            EventGuestQuota(
                event_id=event.id,
                artist_profile_id="artist-a",
                assigned_by_user_id="user-1",
                quota=1,
            ),
            EventGuestlistEntry(
                event_id=event.id,
                guest_user_id="active-quota-guest",
                guest_display_name="Active",
                added_by_user_id="artist-owner",
                added_by_artist_profile_id="artist-b",
            ),
            EventGuestlistEntry(
                event_id=event.id,
                guest_user_id="removed-quota-guest",
                guest_display_name="Removed",
                added_by_user_id="artist-owner",
                added_by_artist_profile_id="artist-b",
                status=GuestlistEntryStatus.removed.value,
            ),
        ]
    )
    session.commit()
    monkeypatch.setattr(users_client, "check_page_role", lambda *_args: "admin")

    response = TestClient(app).get(
        "/v1/events/warehouse-signal/viewer-context", headers=USER_HEADERS
    )

    assert response.status_code == 200
    summaries = response.json()["quota_summaries"]
    assert [item["artist_profile_id"] for item in summaries] == ["artist-a", "artist-b"]
    assert summaries[0]["used"] == 0
    assert summaries[1]["used"] == 1
    assert summaries[1]["remaining"] == 2


def test_guestlist_read_is_manager_only_minimal_and_deterministic(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = session.scalar(select(Event).where(Event.slug == "warehouse-signal"))
    assert event is not None
    created_at = datetime(2026, 7, 1, tzinfo=UTC)
    session.add_all(
        [
            EventGuestlistEntry(
                id="entry-b",
                event_id=event.id,
                guest_user_id="guest-b",
                guest_username="guestb",
                guest_display_name="Guest B",
                added_by_user_id="user-1",
                created_at=created_at,
            ),
            EventGuestlistEntry(
                id="entry-a",
                event_id=event.id,
                guest_user_id="guest-a",
                guest_username="guesta",
                guest_display_name="Guest A",
                added_by_user_id="user-1",
                status=GuestlistEntryStatus.removed.value,
                created_at=created_at,
            ),
        ]
    )
    session.commit()
    monkeypatch.setattr(
        users_client,
        "check_page_role",
        lambda _settings, _page_id, user_id: "editor" if user_id == "user-1" else None,
    )
    client = TestClient(app)

    forbidden = client.get("/v1/events/warehouse-signal/guestlist", headers=USER_2_HEADERS)
    allowed = client.get("/v1/events/warehouse-signal/guestlist", headers=USER_HEADERS)

    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert [entry["id"] for entry in allowed.json()] == ["entry-a", "entry-b"]
    assert [entry["guest_user_id"] for entry in allowed.json()] == ["guest-a", "guest-b"]
    assert [entry["status"] for entry in allowed.json()] == ["removed", "active"]
    assert set(allowed.json()[0]) == {
        "id",
        "guest_user_id",
        "username",
        "display_name",
        "source",
        "status",
        "checked_in_at",
    }
