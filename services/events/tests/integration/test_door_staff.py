from datetime import UTC, datetime
from typing import Any

import pytest
from events.api import routes
from events.domain.models import Event, EventAccessAuditLog, EventDoorStaff
from events.main import app
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from events import users_client

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
MANAGER_HEADERS = {**TOKEN_HEADERS, "X-Threshold-User-Id": "user-1"}
DOOR_HEADERS = {**TOKEN_HEADERS, "X-Threshold-User-Id": "door-user"}
OTHER_HEADERS = {**TOKEN_HEADERS, "X-Threshold-User-Id": "user-2"}


@pytest.fixture(autouse=True)
def door_staff_users(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    refs = {
        "alpha-user": {
            "user_id": "alpha-user",
            "username": "alpha",
            "display_name": "Alpha Door",
        },
        "beta-user": {
            "user_id": "beta-user",
            "username": "beta",
            "display_name": "Beta Door",
        },
        "door-user": {
            "user_id": "door-user",
            "username": "door",
            "display_name": "Door Person",
        },
    }
    by_username = {ref["username"]: ref["user_id"] for ref in refs.values()}
    active = set(refs)

    def get_user(_settings: object, username: str) -> dict[str, str] | None:
        user_id = by_username.get(username.strip().lower())
        return refs.get(user_id) if user_id in active else None

    def get_active(_settings: object, user_ids: list[str]) -> dict[str, dict[str, str]]:
        return {user_id: refs[user_id] for user_id in user_ids if user_id in active}

    monkeypatch.setattr(
        users_client,
        "check_page_role",
        lambda _settings, _page_id, user_id: "admin" if user_id == "user-1" else None,
    )
    monkeypatch.setattr(users_client, "get_user_by_username", get_user)
    monkeypatch.setattr(users_client, "get_active_user_refs", get_active)
    monkeypatch.setattr(users_client, "notify_user", lambda *_args, **_kwargs: True)
    return {"refs": refs, "by_username": by_username, "active": active}


def _assign(client: TestClient, username: str = "door"):
    return client.put(
        f"/v1/events/warehouse-signal/door-staff/by-username/{username}",
        headers=MANAGER_HEADERS,
    )


def _add_guest_and_mint_token(
    client: TestClient,
    slug: str = "warehouse-signal",
    guest_user_id: str | None = None,
) -> str:
    guest_user_id = guest_user_id or f"{slug}-guest"
    added = client.post(
        f"/v1/events/{slug}/guestlist",
        headers=MANAGER_HEADERS,
        json={
            "user_id": guest_user_id,
            "username": f"{guest_user_id}-name",
            "display_name": "Door Guest",
        },
    )
    assert added.status_code == 201
    token = client.post(
        f"/v1/events/{slug}/guestlist/me/qr-token",
        headers={**TOKEN_HEADERS, "X-Threshold-User-Id": guest_user_id},
    )
    assert token.status_code == 201
    return token.json()["token"]


def test_assignment_and_assignment_id_delete_are_idempotent_and_audited(
    session: Session,
) -> None:
    client = TestClient(app)
    beta = _assign(client, "beta")
    alpha = _assign(client, "alpha")
    duplicate = _assign(client, "ALPHA")
    listed = client.get("/v1/events/warehouse-signal/door-staff", headers=MANAGER_HEADERS)

    assert beta.status_code == 200
    assert alpha.status_code == 200
    assert duplicate.json() == alpha.json()
    expected = sorted(
        [beta.json(), alpha.json()],
        key=lambda row: (row["assigned_at"], row["id"]),
    )
    assert [row["id"] for row in listed.json()] == [row["id"] for row in expected]
    assert set(listed.json()[0]) == {"id", "username", "display_name", "assigned_at"}
    assert session.scalar(select(func.count(EventDoorStaff.id))) == 2

    revoked = client.delete(
        f"/v1/events/warehouse-signal/door-staff/{alpha.json()['id']}",
        headers=MANAGER_HEADERS,
    )
    repeated = client.delete(
        f"/v1/events/warehouse-signal/door-staff/{alpha.json()['id']}",
        headers=MANAGER_HEADERS,
    )
    cross_event_missing = client.delete(
        f"/v1/events/missing-event/door-staff/{beta.json()['id']}",
        headers=MANAGER_HEADERS,
    )
    audits = session.scalars(
        select(EventAccessAuditLog).where(
            EventAccessAuditLog.action.in_(["door_staff.assigned", "door_staff.revoked"])
        )
    ).all()

    assert revoked.status_code == 204
    assert repeated.status_code == 204
    assert cross_event_missing.status_code == 404
    assert [audit.action for audit in audits].count("door_staff.assigned") == 2
    assert [audit.action for audit in audits].count("door_staff.revoked") == 1


def test_concurrent_assignment_conflict_returns_existing_transition(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = session.scalar(select(Event).where(Event.slug == "warehouse-signal"))
    assert event is not None
    existing = EventDoorStaff(
        event_id=event.id,
        user_id="door-user",
        assigned_by_user_id="user-1",
    )
    session.add(existing)
    session.commit()
    original_scalar = session.scalar
    scalar_calls = 0

    def miss_then_read(statement: Any) -> Any:
        nonlocal scalar_calls
        scalar_calls += 1
        return None if scalar_calls == 1 else original_scalar(statement)

    monkeypatch.setattr(session, "scalar", miss_then_read)
    result, created = routes._get_or_create_door_staff(
        session,
        event_id=event.id,
        user_id="door-user",
        assigned_by_user_id="user-1",
    )

    assert created is False
    assert result.id == existing.id
    assert original_scalar(select(func.count(EventDoorStaff.id))) == 1


def test_assignment_requires_manager_and_active_user(
    session: Session,
    door_staff_users: dict[str, Any],
) -> None:
    door_staff_users["by_username"].update(
        {"locked": "locked-user", "deleted": "deleted-user"}
    )
    door_staff_users["refs"].update(
        {
            "locked-user": {
                "user_id": "locked-user",
                "username": "locked",
                "display_name": "Locked",
            },
            "deleted-user": {
                "user_id": "deleted-user",
                "username": "deleted",
                "display_name": "Deleted",
            },
        }
    )
    client = TestClient(app)

    forbidden = client.put(
        "/v1/events/warehouse-signal/door-staff/by-username/door",
        headers=OTHER_HEADERS,
    )
    locked = _assign(client, "locked")
    deleted = _assign(client, "deleted")
    unknown = _assign(client, "unknown")

    assert forbidden.status_code == 403
    assert locked.status_code == 404
    assert deleted.status_code == 404
    assert unknown.status_code == 404
    assert session.scalar(select(EventDoorStaff)) is None


def test_username_rename_and_reuse_do_not_change_assignment_identity(
    session: Session,
    door_staff_users: dict[str, Any],
) -> None:
    client = TestClient(app)
    original = _assign(client)
    original_id = original.json()["id"]
    refs = door_staff_users["refs"]
    refs["door-user"]["username"] = "renamed-door"
    refs["door-user"]["display_name"] = "Renamed Door"
    refs["replacement-user"] = {
        "user_id": "replacement-user",
        "username": "door",
        "display_name": "Replacement Door",
    }
    door_staff_users["active"].add("replacement-user")
    door_staff_users["by_username"]["door"] = "replacement-user"

    renamed_list = client.get(
        "/v1/events/warehouse-signal/door-staff", headers=MANAGER_HEADERS
    )
    replacement = _assign(client)
    client.delete(
        f"/v1/events/warehouse-signal/door-staff/{original_id}",
        headers=MANAGER_HEADERS,
    )
    remaining = client.get(
        "/v1/events/warehouse-signal/door-staff", headers=MANAGER_HEADERS
    )

    assert renamed_list.json()[0]["username"] == "renamed-door"
    assert replacement.json()["id"] != original_id
    assert [row["id"] for row in remaining.json()] == [replacement.json()["id"]]
    assert session.scalar(
        select(EventDoorStaff.user_id).where(EventDoorStaff.id == replacement.json()["id"])
    ) == "replacement-user"


def test_inactive_assignment_is_visible_for_revoke_but_cannot_check_in(
    session: Session,
    door_staff_users: dict[str, Any],
) -> None:
    client = TestClient(app)
    assignment = _assign(client).json()
    door_staff_users["active"].remove("door-user")
    token = _add_guest_and_mint_token(client)

    listed = client.get("/v1/events/warehouse-signal/door-staff", headers=MANAGER_HEADERS)
    context = client.get(
        "/v1/events/warehouse-signal/viewer-context", headers=DOOR_HEADERS
    )
    denied = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=DOOR_HEADERS,
        json={"token": token},
    )
    revoked = client.delete(
        f"/v1/events/warehouse-signal/door-staff/{assignment['id']}",
        headers=MANAGER_HEADERS,
    )

    assert listed.json() == [
        {
            "id": assignment["id"],
            "username": None,
            "display_name": None,
            "assigned_at": assignment["assigned_at"],
        }
    ]
    assert context.json()["can_check_in"] is False
    assert denied.status_code == 403
    assert revoked.status_code == 204


def test_door_staff_has_only_check_in_capability_and_minimal_response(session: Session) -> None:
    client = TestClient(app)
    assignment = _assign(client)
    assert assignment.status_code == 200
    context = client.get(
        "/v1/events/warehouse-signal/viewer-context", headers=DOOR_HEADERS
    )
    guestlist = client.get(
        "/v1/events/warehouse-signal/guestlist", headers=DOOR_HEADERS
    )
    guest_add = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=DOOR_HEADERS,
        json={"user_id": "unauthorized-guest", "display_name": "Unauthorized Guest"},
    )
    update = client.post(
        "/v1/events/warehouse-signal/updates",
        headers=DOOR_HEADERS,
        json={"body": "Unauthorized door update"},
    )
    quota = client.put(
        "/v1/events/warehouse-signal/guestlist/quotas/artist-1",
        headers=DOOR_HEADERS,
        json={"quota": 1},
    )
    door_list = client.get(
        "/v1/events/warehouse-signal/door-staff", headers=DOOR_HEADERS
    )
    door_assign = client.put(
        "/v1/events/warehouse-signal/door-staff/by-username/alpha",
        headers=DOOR_HEADERS,
    )
    door_revoke = client.delete(
        f"/v1/events/warehouse-signal/door-staff/{assignment.json()['id']}",
        headers=DOOR_HEADERS,
    )
    token = _add_guest_and_mint_token(client)
    checked = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=DOOR_HEADERS,
        json={"token": token},
    )

    assert context.status_code == 200
    assert context.json()["can_check_in"] is True
    assert context.json()["can_manage_guestlist"] is False
    assert context.json()["can_set_dj_quota"] is False
    assert context.json()["can_post_update"] is False
    assert guestlist.status_code == 403
    assert guest_add.status_code == 403
    assert update.status_code == 403
    assert quota.status_code == 403
    assert door_list.status_code == 403
    assert door_assign.status_code == 403
    assert door_revoke.status_code == 403
    assert checked.status_code == 200
    assert checked.json() == {
        "status": "checked_in",
        "display_name": "Door Guest",
        "username": "warehouse-signal-guest-name",
    }


def test_door_staff_is_event_scoped(session: Session) -> None:
    client = TestClient(app)
    assignment = _assign(client)
    assert assignment.status_code == 200
    session.add(
        Event(
            slug="second-door-night",
            title="Second Door Night",
            starts_at=datetime(2026, 8, 1, 22, tzinfo=UTC),
            city="Warsaw",
            page_id="00000000-0000-0000-0000-000000000001",
            created_by_user_id="user-1",
        )
    )
    session.commit()
    token = _add_guest_and_mint_token(client, "second-door-night")
    wrong_event_revoke = client.delete(
        f"/v1/events/second-door-night/door-staff/{assignment.json()['id']}",
        headers=MANAGER_HEADERS,
    )

    response = client.post(
        "/v1/events/second-door-night/check-in",
        headers=DOOR_HEADERS,
        json={"token": token},
    )

    assert wrong_event_revoke.status_code == 204
    assert session.get(EventDoorStaff, assignment.json()["id"]) is not None
    assert response.status_code == 403


def test_door_staff_lock_queries_use_postgresql_row_locks() -> None:
    by_user = str(
        routes._door_staff_lock_query("event-1", user_id="door-user").compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    by_assignment = str(
        routes._door_staff_lock_query("event-1", assignment_id="assignment-1").compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "FOR UPDATE" in by_user
    assert "event_door_staff.event_id = 'event-1'" in by_user
    assert "event_door_staff.user_id = 'door-user'" in by_user
    assert "FOR UPDATE" in by_assignment
    assert "event_door_staff.id = 'assignment-1'" in by_assignment
