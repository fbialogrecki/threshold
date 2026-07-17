from datetime import UTC, datetime
from typing import Any

import pytest
from events.domain.models import Event, EventFollow
from events.main import app
from events.main_dependencies import settings
from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from events import users_client

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}


def test_artist_refs_client_makes_one_bounded_stable_batch_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class Response:
        status_code = 200

        def json(self) -> list[dict[str, str]]:
            return []

    def post(_url: str, **kwargs: object) -> Response:
        calls.append(kwargs)
        return Response()

    monkeypatch.setattr(users_client.httpx, "post", post)
    artist_ids = [f"artist-{index}" for index in range(125)]
    users_client.get_artist_refs(settings, [artist_ids[0], *artist_ids, artist_ids[1]])

    assert len(calls) == 1
    assert calls[0]["json"] == {"artist_profile_ids": artist_ids[:100]}


def _event(
    event_id: str,
    slug: str,
    created_at: datetime,
    *,
    city: str = "Berlin",
    page_id: str = "page-other",
    creator_id: str = "creator-other",
    deleted: bool = False,
    secret: bool = False,
) -> Event:
    return Event(
        id=event_id,
        slug=slug,
        title=slug,
        starts_at=datetime(2026, 9, 1, tzinfo=UTC),
        city=city,
        page_id=page_id,
        created_by_user_id=creator_id,
        created_at=created_at,
        deleted_at=created_at if deleted else None,
        location_mode="secret_location" if secret else "public_location",
        venue_name="Hidden" if secret else "Visible",
        address="Secret Street" if secret else "Public Street",
        lineup=[{"name": "Stored Artist", "artist_profile_id": "artist-1"}],
    )


def test_feed_candidates_requires_internal_token_and_validates_bounds(session: Session) -> None:
    client = TestClient(app)
    path = "/internal/v1/events/feed-candidates"

    assert client.post(path, json={}).status_code == 401
    assert (
        client.post(
            path,
            headers={"X-Threshold-User-Id": "viewer-1"},
            json={},
        ).status_code
        == 401
    )
    assert (
        client.post(
            path,
            headers={
                "X-Threshold-Internal-Token": "wrong",
                "X-Threshold-User-Id": "viewer-1",
            },
            json={},
        ).status_code
        == 401
    )
    assert client.post(path, headers=TOKEN_HEADERS, json={}).json() == []
    assert (
        client.post(
            path,
            headers=TOKEN_HEADERS,
            json={"followed_page_ids": ["page"] * 100, "limit": 100},
        ).status_code
        == 200
    )
    assert (
        client.post(
            path,
            headers=TOKEN_HEADERS,
            json={"followed_page_ids": ["page"] * 101},
        ).status_code
        == 422
    )
    assert client.post(path, headers=TOKEN_HEADERS, json={"limit": 101}).status_code == 422
    assert client.post(path, headers=TOKEN_HEADERS, json={"city": " "}).status_code == 422
    assert (
        client.post(
            path,
            headers=TOKEN_HEADERS,
            json={"followed_event_ids": ["untrusted-event"]},
        ).status_code
        == 422
    )


def test_feed_candidates_or_admission_order_one_query_and_secret_redaction(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.query(Event).delete()
    session.add_all(
        [
            _event("city", "city", datetime(2026, 7, 1, tzinfo=UTC), city="Berlin"),
            _event(
                "page",
                "page",
                datetime(2026, 7, 4, tzinfo=UTC),
                page_id="followed-page",
                secret=True,
            ),
            _event(
                "creator",
                "creator",
                datetime(2026, 7, 3, tzinfo=UTC),
                creator_id="followed-creator",
            ),
            _event("event", "event", datetime(2026, 7, 2, tzinfo=UTC)),
            _event("outside", "outside", datetime(2026, 7, 6, tzinfo=UTC), city="Paris"),
            _event(
                "deleted",
                "deleted",
                datetime(2026, 7, 5, tzinfo=UTC),
                city="Berlin",
                deleted=True,
            ),
        ]
    )
    session.add(EventFollow(event_id="event", user_id="viewer-1"))
    session.commit()
    artist_calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        users_client,
        "get_artist_refs",
        lambda _settings, ids: artist_calls.append(("batch", ids)) or {},
    )
    monkeypatch.setattr(
        users_client,
        "get_artist_ref",
        lambda _settings, artist_id: artist_calls.append(("single", artist_id)),
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
        response = TestClient(app).post(
            "/internal/v1/events/feed-candidates",
            headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "viewer-1"},
            json={
                "city": "berlin",
                "followed_page_ids": ["followed-page", "followed-page"],
                "followed_creator_user_ids": ["followed-creator"],
                "limit": 4,
            },
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == ["page", "creator", "event", "city"]
    assert body[0]["venue_name"] is None
    assert body[0]["address"] is None
    assert body[0]["lineup"][0]["name"] == "Stored Artist"
    assert body[2]["is_following"] is True
    assert artist_calls == []
    assert len(selects) == 1


def test_feed_candidates_omit_follow_admission_without_viewer_and_reject_spoofing(
    session: Session,
) -> None:
    session.query(Event).delete()
    attached = _event(
        "attached-event",
        "attached-event",
        datetime(2026, 7, 1, tzinfo=UTC),
        city="Paris",
    )
    session.add_all(
        [
            attached,
            EventFollow(event_id=attached.id, user_id="viewer-1"),
        ]
    )
    session.commit()
    client = TestClient(app)

    anonymous = client.post(
        "/internal/v1/events/feed-candidates",
        headers=TOKEN_HEADERS,
        json={},
    )
    spoofed = client.post(
        "/internal/v1/events/feed-candidates",
        headers=TOKEN_HEADERS,
        json={"followed_event_ids": [attached.id]},
    )
    viewer = client.post(
        "/internal/v1/events/feed-candidates",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": "viewer-1"},
        json={},
    )

    assert anonymous.status_code == 200
    assert anonymous.json() == []
    assert spoofed.status_code == 422
    assert [event["id"] for event in viewer.json()] == [attached.id]


def test_regular_event_list_batches_unique_artist_references(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = session.query(Event).filter_by(slug="warehouse-signal").one()
    first.lineup = [{"name": "Stored One", "artist_profile_id": "artist-1"}]
    session.add(
        _event(
            "second",
            "second-event",
            datetime(2026, 7, 2, tzinfo=UTC),
        )
    )
    session.commit()
    calls: list[list[str]] = []
    single_calls: list[str] = []

    def get_refs(_settings: object, ids: list[str]) -> dict[str, dict[str, str]]:
        calls.append(ids)
        return {
            "artist-1": {
                "artist_profile_id": "artist-1",
                "user_id": "artist-user",
                "owner_user_id": "artist-user",
                "username": "artist",
                "display_name": "Artist",
                "target_url": "/u/artist",
            }
        }

    monkeypatch.setattr(users_client, "get_artist_refs", get_refs)
    monkeypatch.setattr(
        users_client,
        "get_artist_ref",
        lambda _settings, artist_id: single_calls.append(artist_id),
    )
    response = TestClient(app).get("/v1/events?sort=created", headers=TOKEN_HEADERS)

    assert response.status_code == 200
    assert calls == [["artist-1"]]
    assert single_calls == []
    assert all(
        item["lineup"][0]["artist_handle"] == "artist"
        for item in response.json()["items"]
    )


def test_event_list_enriches_first_100_unique_artists_and_keeps_fallback(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.query(Event).delete()
    first = _event("first", "first-event", datetime(2026, 7, 2, tzinfo=UTC))
    first.lineup = [
        {"name": f"Artist {index}", "artist_profile_id": f"artist-{index}"}
        for index in range(100)
    ]
    second = _event("second", "second-event", datetime(2026, 7, 1, tzinfo=UTC))
    second.lineup = [
        {
            "name": "Stored 100",
            "artist_profile_id": "artist-100",
            "artist_handle": "stored-100",
            "display_name": "Stored Artist 100",
            "target_url": "/u/stored-100",
        }
    ]
    session.add_all([first, second])
    session.commit()
    calls: list[list[str]] = []
    single_calls: list[str] = []

    def get_refs(_settings: object, ids: list[str]) -> dict[str, dict[str, str]]:
        calls.append(ids)
        return {
            artist_id: {
                "artist_profile_id": artist_id,
                "user_id": f"user-{artist_id}",
                "owner_user_id": f"user-{artist_id}",
                "username": f"canonical-{artist_id}",
                "display_name": f"Canonical {artist_id}",
                "target_url": f"/u/canonical-{artist_id}",
            }
            for artist_id in ids
        }

    monkeypatch.setattr(users_client, "get_artist_refs", get_refs)
    monkeypatch.setattr(
        users_client,
        "get_artist_ref",
        lambda _settings, artist_id: single_calls.append(artist_id),
    )
    response = TestClient(app).get("/v1/events?sort=created", headers=TOKEN_HEADERS)

    assert response.status_code == 200
    assert calls == [[f"artist-{index}" for index in range(100)]]
    assert single_calls == []
    assert response.json()["items"][1]["lineup"] == second.lineup
