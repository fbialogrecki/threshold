from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from users.domain.models import ApplicationUser, ArtistProfile, ConsumerProfile
from users.main import app

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
ARTIST_ONE = "11111111-1111-4111-8111-111111111111"
ARTIST_TWO = "22222222-2222-4222-8222-222222222222"
ARTIST_LOCKED = "33333333-3333-4333-8333-333333333333"


def test_artist_refs_requires_internal_token_and_validates_bounds(session: Session) -> None:
    client = TestClient(app)

    assert client.post("/internal/v1/artist-profiles/batch", json={}).status_code == 401
    assert (
        client.post(
            "/internal/v1/artist-profiles/batch",
            headers=TOKEN_HEADERS,
            json={"artist_profile_ids": [ARTIST_ONE] * 100},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/internal/v1/artist-profiles/batch",
            headers=TOKEN_HEADERS,
            json={"artist_profile_ids": [ARTIST_ONE] * 101},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/internal/v1/artist-profiles/batch",
            headers=TOKEN_HEADERS,
            json={"artist_profile_ids": [], "include_deleted": True},
        ).status_code
        == 422
    )


def test_artist_refs_filters_active_users_preserves_order_and_uses_one_query(
    session: Session,
) -> None:
    users = [
        ApplicationUser(id="user-1", username="first", username_normalized="first"),
        ApplicationUser(id="user-2", username="second", username_normalized="second"),
        ApplicationUser(
            id="user-locked",
            username="locked",
            username_normalized="locked",
            status="locked",
        ),
    ]
    session.add_all(users)
    session.flush()
    session.add_all(
        [
            ConsumerProfile(user_id="user-1", display_name="First Artist"),
            ArtistProfile(id=ARTIST_ONE, user_id="user-1"),
            ArtistProfile(id=ARTIST_TWO, user_id="user-2"),
            ArtistProfile(id=ARTIST_LOCKED, user_id="user-locked"),
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
            "/internal/v1/artist-profiles/batch",
            headers=TOKEN_HEADERS,
            json={
                "artist_profile_ids": [
                    ARTIST_TWO,
                    ARTIST_LOCKED,
                    ARTIST_ONE,
                    ARTIST_TWO,
                ]
            },
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200
    assert response.json() == [
        {
            "artist_profile_id": ARTIST_TWO,
            "user_id": "user-2",
            "owner_user_id": "user-2",
            "username": "second",
            "display_name": "second",
            "target_url": "/u/second",
        },
        {
            "artist_profile_id": ARTIST_ONE,
            "user_id": "user-1",
            "owner_user_id": "user-1",
            "username": "first",
            "display_name": "First Artist",
            "target_url": "/u/first",
        },
    ]
    assert len(selects) == 1
