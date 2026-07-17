from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from users.domain.models import Page
from users.main import app

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
PAGE_ONE_ID = "11111111-1111-4111-8111-111111111111"
PAGE_TWO_ID = "22222222-2222-4222-8222-222222222222"
MISSING_PAGE_ID = "00000000-0000-0000-0000-000000000000"


def test_organizer_refs_requires_internal_token(session: Session) -> None:
    response = TestClient(app).post(
        "/internal/v1/pages/organizer-refs",
        json={"page_ids": []},
    )

    assert response.status_code == 401


def test_organizer_refs_empty_input_returns_empty(session: Session) -> None:
    response = TestClient(app).post(
        "/internal/v1/pages/organizer-refs",
        headers=TOKEN_HEADERS,
        json={"page_ids": []},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_organizer_refs_strictly_validates_request(session: Session) -> None:
    client = TestClient(app)

    malformed = client.post(
        "/internal/v1/pages/organizer-refs",
        headers=TOKEN_HEADERS,
        json={"page_ids": ["not-a-page-id"]},
    )
    boundary = client.post(
        "/internal/v1/pages/organizer-refs",
        headers=TOKEN_HEADERS,
        json={"page_ids": [PAGE_ONE_ID] * 100},
    )
    too_many = client.post(
        "/internal/v1/pages/organizer-refs",
        headers=TOKEN_HEADERS,
        json={"page_ids": [PAGE_ONE_ID] * 101},
    )
    extra = client.post(
        "/internal/v1/pages/organizer-refs",
        headers=TOKEN_HEADERS,
        json={"page_ids": [], "include_memberships": True},
    )

    assert malformed.status_code == 422
    assert boundary.status_code == 200
    assert too_many.status_code == 422
    assert extra.status_code == 422


def test_organizer_refs_batches_and_preserves_first_input_order(session: Session) -> None:
    session.add_all(
        [
            Page(
                id=PAGE_ONE_ID,
                slug="first-page",
                display_name="First Page",
                page_type="collective",
            ),
            Page(
                id=PAGE_TWO_ID,
                slug="second-page",
                display_name="Second Page",
                page_type="club",
                avatar_media_asset_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            ),
        ]
    )
    session.commit()
    engine = session.get_bind()
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

    event.listen(engine, "before_cursor_execute", capture_select)
    try:
        response = TestClient(app).post(
            "/internal/v1/pages/organizer-refs",
            headers=TOKEN_HEADERS,
            json={
                "page_ids": [
                    PAGE_TWO_ID,
                    MISSING_PAGE_ID,
                    PAGE_ONE_ID,
                    PAGE_TWO_ID,
                ]
            },
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": PAGE_TWO_ID,
            "slug": "second-page",
            "display_name": "Second Page",
            "page_type": "club",
            "avatar_media_asset_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "target_url": "/pages/second-page",
        },
        {
            "id": PAGE_ONE_ID,
            "slug": "first-page",
            "display_name": "First Page",
            "page_type": "collective",
            "avatar_media_asset_id": None,
            "target_url": "/pages/first-page",
        },
    ]
    assert len(selects) == 1
