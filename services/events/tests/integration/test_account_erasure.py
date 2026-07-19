from datetime import UTC, datetime, timedelta

from events.domain.models import (
    AccountErasureTombstone,
    Event,
    EventAccessAuditLog,
    EventBoost,
    EventCheckInToken,
    EventDoorStaff,
    EventFollow,
    EventGuestlistEntry,
    EventGuestQuota,
    EventUpdate,
)
from events.main import app
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}


def test_internal_account_erasure_removes_participation_and_anonymizes_attribution(
    session: Session,
) -> None:
    event = session.scalar(select(Event).where(Event.slug == "warehouse-signal"))
    assert event is not None
    target_user_id = "user-1"
    other_user_id = "user-2"
    event.poster_media_asset_id = "asset-owned-by-user-1"
    event.lineup = [
        {"name": "Delete Me", "artist_profile_id": "artist-user-1"},
        {"name": "Retained", "artist_profile_id": "artist-user-2"},
    ]

    update = EventUpdate(
        event_id=event.id,
        author_user_id=target_user_id,
        author_page_id=event.page_id,
        body="The event content remains.",
    )
    target_guest = EventGuestlistEntry(
        id="target-guest-entry",
        event_id=event.id,
        guest_user_id=target_user_id,
        guest_username="delete-me",
        guest_display_name="Delete Me",
        added_by_user_id=other_user_id,
    )
    retained_guest = EventGuestlistEntry(
        event_id=event.id,
        guest_user_id="guest-2",
        guest_username="retained",
        guest_display_name="Retained Guest",
        added_by_user_id=target_user_id,
        checked_in_by_user_id=target_user_id,
    )
    target_door_staff = EventDoorStaff(
        event_id=event.id,
        user_id=target_user_id,
        assigned_by_user_id=other_user_id,
    )
    retained_door_staff = EventDoorStaff(
        event_id=event.id,
        user_id="door-2",
        assigned_by_user_id=target_user_id,
    )
    quota = EventGuestQuota(
        event_id=event.id,
        artist_profile_id="artist-1",
        quota=2,
        assigned_by_user_id=target_user_id,
    )
    audit = EventAccessAuditLog(
        event_id=event.id,
        actor_user_id=target_user_id,
        action="guestlist.added",
        target_type="event_guestlist",
        target_id=target_guest.id,
        metadata_json={
            "guest_user_id": target_user_id,
            "nested": {"participants": [target_user_id, other_user_id]},
            "safe": "retained",
        },
    )
    session.add_all(
        [
            update,
            EventFollow(event_id=event.id, user_id=target_user_id),
            EventBoost(event_id=event.id, user_id=target_user_id),
            target_guest,
            retained_guest,
            target_door_staff,
            retained_door_staff,
            quota,
            audit,
        ]
    )
    session.flush()
    token = EventCheckInToken(
        event_id=event.id,
        guestlist_entry_id=target_guest.id,
        token_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    session.add(token)
    session.commit()
    event_id = event.id
    update_id = update.id
    target_guest_id = target_guest.id
    token_id = token.id
    target_door_staff_id = target_door_staff.id
    retained_guest_id = retained_guest.id
    retained_door_staff_id = retained_door_staff.id
    quota_id = quota.id
    audit_id = audit.id

    client = TestClient(app)
    first = client.post(
        "/internal/v1/account-erasure",
        headers=TOKEN_HEADERS,
        json={"user_id": target_user_id, "artist_profile_ids": ["artist-user-1"]},
    )
    second = client.post(
        "/internal/v1/account-erasure",
        headers=TOKEN_HEADERS,
        json={"user_id": target_user_id, "artist_profile_ids": ["artist-user-1"]},
    )

    assert first.status_code == 200
    assert first.json() == {"status": "ok"}
    assert second.status_code == 200
    session.expire_all()
    tombstones = session.scalars(
        select(AccountErasureTombstone).where(
            AccountErasureTombstone.user_id == target_user_id
        )
    ).all()
    assert len(tombstones) == 1
    erased_event = session.get(Event, event_id)
    assert erased_event is not None
    assert erased_event.created_by_user_id == "deleted-user"
    assert erased_event.poster_media_asset_id is None
    assert erased_event.lineup == [
        {"name": "Deleted Artist"},
        {"name": "Retained", "artist_profile_id": "artist-user-2"},
    ]
    assert session.get(EventUpdate, update_id) is not None
    assert session.get(EventUpdate, update_id).body == "The event content remains."
    assert session.get(EventUpdate, update_id).author_user_id == "deleted-user"
    assert (
        session.scalars(select(EventFollow).where(EventFollow.user_id == target_user_id)).all()
        == []
    )
    assert (
        session.scalars(select(EventBoost).where(EventBoost.user_id == target_user_id)).all()
        == []
    )
    assert session.get(EventGuestlistEntry, target_guest_id) is None
    assert session.get(EventCheckInToken, token_id) is None
    assert session.get(EventDoorStaff, target_door_staff_id) is None

    kept_guest = session.get(EventGuestlistEntry, retained_guest_id)
    assert kept_guest is not None
    assert kept_guest.added_by_user_id == "deleted-user"
    assert kept_guest.checked_in_by_user_id is None
    kept_staff = session.get(EventDoorStaff, retained_door_staff_id)
    assert kept_staff is not None
    assert kept_staff.assigned_by_user_id == "deleted-user"
    assert session.get(EventGuestQuota, quota_id).assigned_by_user_id == "deleted-user"
    scrubbed_audit = session.get(EventAccessAuditLog, audit_id)
    assert scrubbed_audit is not None
    assert scrubbed_audit.actor_user_id is None
    assert scrubbed_audit.metadata_json == {
        "guest_user_id": None,
        "nested": {"participants": [None, other_user_id]},
        "safe": "retained",
    }


def test_internal_account_erasure_requires_internal_token() -> None:
    response = TestClient(app).post(
        "/internal/v1/account-erasure",
        json={"user_id": "user-1"},
    )

    assert response.status_code == 401


def test_erased_user_cannot_create_event(session: Session) -> None:
    client = TestClient(app)
    erased = client.post(
        "/internal/v1/account-erasure",
        headers=TOKEN_HEADERS,
        json={"user_id": "erased-creator"},
    )

    response = client.post(
        "/v1/events",
        headers={
            **TOKEN_HEADERS,
            "X-Threshold-User-Id": "erased-creator",
            "X-Threshold-Username": "erased",
            "X-Threshold-Display-Name": "Erased Creator",
        },
        json={
            "title": "Must Not Exist",
            "slug": "must-not-exist",
            "starts_at": "2026-08-15T20:00:00Z",
            "city": "Berlin",
            "page_id": "00000000-0000-0000-0000-000000000001",
        },
    )

    assert erased.status_code == 200
    assert response.status_code == 409
    assert response.json() == {"detail": "account has been erased"}
    assert session.scalar(select(Event).where(Event.slug == "must-not-exist")) is None


def test_guestlist_write_rejects_erased_actor_or_target(session: Session) -> None:
    client = TestClient(app)
    for user_id in ("erased-manager", "erased-guest"):
        response = client.post(
            "/internal/v1/account-erasure",
            headers=TOKEN_HEADERS,
            json={"user_id": user_id},
        )
        assert response.status_code == 200

    manager_headers = {
        **TOKEN_HEADERS,
        "X-Threshold-User-Id": "user-1",
        "X-Threshold-Username": "manager",
        "X-Threshold-Display-Name": "Manager",
    }
    erased_manager_headers = {
        **manager_headers,
        "X-Threshold-User-Id": "erased-manager",
    }

    erased_target = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=manager_headers,
        json={"user_id": "erased-guest", "display_name": "Erased Guest"},
    )
    erased_actor = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=erased_manager_headers,
        json={"user_id": "active-guest", "display_name": "Active Guest"},
    )

    assert erased_target.status_code == 409
    assert erased_actor.status_code == 409
    assert session.scalars(
        select(EventGuestlistEntry).where(
            EventGuestlistEntry.guest_user_id.in_(["erased-guest", "active-guest"])
        )
    ).all() == []


def test_erased_actor_cannot_write_update_follow_or_boost(session: Session) -> None:
    client = TestClient(app)
    headers = {
        **TOKEN_HEADERS,
        "X-Threshold-User-Id": "user-1",
        "X-Threshold-Username": "manager",
        "X-Threshold-Display-Name": "Manager",
    }
    erased = client.post(
        "/internal/v1/account-erasure",
        headers=TOKEN_HEADERS,
        json={"user_id": "user-1"},
    )

    responses = [
        client.patch(
            "/v1/events/warehouse-signal",
            headers=headers,
            json={"title": "must not be retained"},
        ),
        client.post(
            "/v1/events/warehouse-signal/updates",
            headers=headers,
            json={"body": "must not be retained"},
        ),
        client.post("/v1/events/warehouse-signal/follow", headers=headers),
        client.post("/v1/events/warehouse-signal/boost", headers=headers),
    ]

    assert erased.status_code == 200
    assert [response.status_code for response in responses] == [409, 409, 409, 409]
    assert session.scalars(
        select(EventUpdate).where(EventUpdate.author_user_id == "user-1")
    ).all() == []
    assert session.scalars(select(EventFollow).where(EventFollow.user_id == "user-1")).all() == []
    assert session.scalars(select(EventBoost).where(EventBoost.user_id == "user-1")).all() == []
