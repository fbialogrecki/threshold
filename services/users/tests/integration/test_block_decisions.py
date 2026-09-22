from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session
from users.domain.models import ApplicationUser, UserBlock
from users.main import app

URL = "/internal/v1/users/block-decisions"
HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
VIEWER = "11111111-1111-4111-8111-111111111111"
TARGET = "22222222-2222-4222-8222-222222222222"


def seed(session: Session) -> None:
    session.add_all([ApplicationUser(id=VIEWER), ApplicationUser(id=TARGET)])
    session.commit()


@pytest.mark.parametrize("reverse", [False, True])
def test_either_direction_denies(session: Session, reverse: bool) -> None:
    seed(session)
    pair = (TARGET, VIEWER) if reverse else (VIEWER, TARGET)
    session.add(UserBlock(blocker_user_id=pair[0], blocked_user_id=pair[1]))
    session.commit()
    response = TestClient(app).post(
        URL, headers=HEADERS, json={"viewer_id": VIEWER, "target_ids": [TARGET]}
    )
    assert response.json()["decisions"] == [{"target_id": TARGET, "allowed": False}]


@pytest.mark.parametrize("subject", ["viewer", "target"])
@pytest.mark.parametrize("state", ["unknown", "locked", "erasure_pending", "deleted"])
def test_nonactive_identity_denies(session: Session, subject: str, state: str) -> None:
    seed(session)
    identity = VIEWER if subject == "viewer" else TARGET
    user = session.get(ApplicationUser, identity)
    assert user is not None
    if state == "unknown":
        session.delete(user)
    else:
        user.status = state
    session.commit()
    response = TestClient(app).post(
        URL, headers=HEADERS, json={"viewer_id": VIEWER, "target_ids": [TARGET]}
    )
    assert response.json()["decisions"] == [{"target_id": TARGET, "allowed": False}]


@pytest.mark.parametrize("size", [1, 100])
@pytest.mark.parametrize("duplicates", [True, False])
def test_bounded_query_count_preserves_duplicates(
    session: Session, size: int, duplicates: bool
) -> None:
    seed(session)
    targets = [TARGET] * size if duplicates else [str(uuid4()) for _ in range(size)]
    if not duplicates:
        session.add_all(ApplicationUser(id=target) for target in targets)
        session.commit()
    statements = []

    def capture(_conn: Any, _cursor: Any, statement: str, *args: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = TestClient(app).post(
            URL, headers=HEADERS, json={"viewer_id": VIEWER, "target_ids": targets}
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert response.json() == {
        "viewer_id": VIEWER,
        "decisions": [{"target_id": target, "allowed": True} for target in targets],
    }
    assert len(statements) == 1


@pytest.mark.parametrize("headers", [{}, {"X-Threshold-Internal-Token": "wrong"}])
def test_auth_required(session: Session, headers: dict[str, str]) -> None:
    assert (
        TestClient(app)
        .post(URL, headers=headers, json={"viewer_id": VIEWER, "target_ids": [TARGET]})
        .status_code
        == 401
    )


@pytest.mark.parametrize("targets", [[], ["x"] * 101, [""], [True], ["x" * 37]])
def test_invalid_targets_rejected(session: Session, targets: list[Any]) -> None:
    assert (
        TestClient(app)
        .post(URL, headers=HEADERS, json={"viewer_id": VIEWER, "target_ids": targets})
        .status_code
        == 422
    )


def test_no_block_is_explicit_allow(session: Session) -> None:
    seed(session)
    response = TestClient(app).post(
        URL, headers=HEADERS, json={"viewer_id": VIEWER, "target_ids": [TARGET]}
    )
    assert response.status_code == 200
    assert response.json() == {
        "viewer_id": VIEWER,
        "decisions": [{"target_id": TARGET, "allowed": True}],
    }
