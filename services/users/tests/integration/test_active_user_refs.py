from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from users.domain.models import ApplicationUser, ConsumerProfile
from users.main import app

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
ACTIVE_ONE = "11111111-1111-4111-8111-111111111111"
ACTIVE_TWO = "22222222-2222-4222-8222-222222222222"
LOCKED = "33333333-3333-4333-8333-333333333333"
DELETED = "44444444-4444-4444-8444-444444444444"


def test_active_user_refs_requires_internal_token_and_validates_limit(session: Session) -> None:
    client = TestClient(app)

    unauthorized = client.post("/internal/v1/users/active-refs", json={"user_ids": []})
    boundary = client.post(
        "/internal/v1/users/active-refs",
        headers=TOKEN_HEADERS,
        json={"user_ids": [ACTIVE_ONE] * 100},
    )
    too_many = client.post(
        "/internal/v1/users/active-refs",
        headers=TOKEN_HEADERS,
        json={"user_ids": [ACTIVE_ONE] * 101},
    )
    malformed = client.post(
        "/internal/v1/users/active-refs",
        headers=TOKEN_HEADERS,
        json={"user_ids": [""]},
    )
    extra = client.post(
        "/internal/v1/users/active-refs",
        headers=TOKEN_HEADERS,
        json={"user_ids": [], "include_locked": True},
    )

    assert unauthorized.status_code == 401
    assert boundary.status_code == 200
    assert too_many.status_code == 422
    assert malformed.status_code == 422
    assert extra.status_code == 422


def test_active_user_refs_filters_status_batches_and_preserves_order(session: Session) -> None:
    session.add_all(
        [
            ApplicationUser(
                id=ACTIVE_ONE,
                username="activeone",
                username_normalized="activeone",
            ),
            ApplicationUser(
                id=ACTIVE_TWO,
                username="activetwo",
                username_normalized="activetwo",
            ),
            ApplicationUser(
                id=LOCKED,
                username="locked",
                username_normalized="locked",
                status="locked",
            ),
            ApplicationUser(
                id=DELETED,
                username="deleted",
                username_normalized="deleted",
                status="deleted",
            ),
            ConsumerProfile(user_id=ACTIVE_ONE, display_name="Active One"),
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
            "/internal/v1/users/active-refs",
            headers=TOKEN_HEADERS,
            json={"user_ids": [ACTIVE_TWO, LOCKED, ACTIVE_ONE, DELETED, ACTIVE_TWO]},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200
    assert response.json() == [
        {"id": ACTIVE_TWO, "username": "activetwo", "display_name": "activetwo"},
        {"id": ACTIVE_ONE, "username": "activeone", "display_name": "Active One"},
    ]
    assert len(selects) == 1
