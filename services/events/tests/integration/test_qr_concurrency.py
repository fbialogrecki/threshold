from datetime import timedelta
from typing import Any

import pytest
from events.api import routes
from events.domain.models import (
    CheckInStatus,
    Event,
    EventAccessAuditLog,
    EventCheckInToken,
    EventGuestlistEntry,
    utc_now,
)
from events.main import app
from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
MANAGER_HEADERS = {**TOKEN_HEADERS, "X-Threshold-User-Id": "user-1"}


def _event(session: Session) -> Event:
    event = session.scalar(select(Event).where(Event.slug == "warehouse-signal"))
    assert event is not None
    return event


def _drop_issued_index(session: Session) -> None:
    session.execute(text("DROP INDEX uq_event_check_in_tokens_one_issued"))
    session.commit()


def _legacy_entry_with_tokens(
    session: Session, *, checked_in: bool = False
) -> tuple[EventGuestlistEntry, str, str]:
    event = _event(session)
    entry = EventGuestlistEntry(
        event_id=event.id,
        guest_user_id="legacy-guest",
        guest_username="legacyguest",
        guest_display_name="Legacy Guest",
        added_by_user_id="user-1",
        checked_in_at=utc_now() if checked_in else None,
        checked_in_by_user_id="user-1" if checked_in else None,
    )
    session.add(entry)
    session.flush()
    first = "legacy-first-token-value"
    second = "legacy-second-token-value"
    session.add_all(
        [
            EventCheckInToken(
                id="legacy-token-a",
                event_id=event.id,
                guestlist_entry_id=entry.id,
                token_hash=routes._token_hash(first),
                status=CheckInStatus.used.value if checked_in else CheckInStatus.issued.value,
                expires_at=utc_now() + timedelta(minutes=5),
                used_at=utc_now() if checked_in else None,
            ),
            EventCheckInToken(
                id="legacy-token-b",
                event_id=event.id,
                guestlist_entry_id=entry.id,
                token_hash=routes._token_hash(second),
                expires_at=utc_now() + timedelta(minutes=5),
            ),
        ]
    )
    if checked_in:
        session.add(
            EventAccessAuditLog(
                event_id=event.id,
                actor_user_id="user-1",
                action="guestlist.checked_in",
                target_type="event_guestlist",
                target_id=entry.id,
                metadata_json={"guest_user_id": entry.guest_user_id},
            )
        )
    session.commit()
    return entry, first, second


def test_two_legacy_issued_tokens_allow_one_check_in_and_one_audit(
    session: Session,
) -> None:
    _drop_issued_index(session)
    entry, first, second = _legacy_entry_with_tokens(session)
    client = TestClient(app)

    winner = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=MANAGER_HEADERS,
        json={"token": first},
    )
    loser = client.post(
        "/v1/events/warehouse-signal/check-in",
        headers=MANAGER_HEADERS,
        json={"token": second},
    )
    session.expire_all()
    tokens = {
        token.id: token.status
        for token in session.scalars(
            select(EventCheckInToken).where(
                EventCheckInToken.guestlist_entry_id == entry.id
            )
        )
    }
    audits = session.scalars(
        select(EventAccessAuditLog).where(
            EventAccessAuditLog.action == "guestlist.checked_in",
            EventAccessAuditLog.target_id == entry.id,
        )
    ).all()

    assert winner.status_code == 200
    assert winner.json() == {
        "status": "checked_in",
        "display_name": "Legacy Guest",
        "username": "legacyguest",
    }
    assert loser.status_code == 409
    assert tokens == {
        "legacy-token-a": CheckInStatus.used.value,
        "legacy-token-b": CheckInStatus.revoked.value,
    }
    assert len(audits) == 1


def test_guest_claim_failure_rolls_back_losing_token_and_audit(
    session: Session,
) -> None:
    _drop_issued_index(session)
    entry, _, losing_token = _legacy_entry_with_tokens(session, checked_in=True)
    audits_before = session.scalar(
        select(func.count(EventAccessAuditLog.id)).where(
            EventAccessAuditLog.action == "guestlist.checked_in",
            EventAccessAuditLog.target_id == entry.id,
        )
    )

    response = TestClient(app).post(
        "/v1/events/warehouse-signal/check-in",
        headers=MANAGER_HEADERS,
        json={"token": losing_token},
    )
    session.expire_all()
    losing_row = session.get(EventCheckInToken, "legacy-token-b")
    audits_after = session.scalar(
        select(func.count(EventAccessAuditLog.id)).where(
            EventAccessAuditLog.action == "guestlist.checked_in",
            EventAccessAuditLog.target_id == entry.id,
        )
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "guest already checked in"}
    assert losing_row is not None
    assert losing_row.status == CheckInStatus.issued.value
    assert losing_row.used_at is None
    assert audits_before == audits_after == 1


def test_serialized_mint_keeps_one_issued_token_and_locks_guest_row(
    session: Session,
) -> None:
    client = TestClient(app)
    added = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=MANAGER_HEADERS,
        json={"user_id": "mint-guest", "display_name": "Mint Guest"},
    )
    assert added.status_code == 201
    guest_headers = {**TOKEN_HEADERS, "X-Threshold-User-Id": "mint-guest"}

    first = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers=guest_headers,
    )
    second = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers=guest_headers,
    )
    rows = session.scalars(
        select(EventCheckInToken)
        .where(EventCheckInToken.guestlist_entry_id == added.json()["id"])
        .order_by(EventCheckInToken.created_at.asc(), EventCheckInToken.id.asc())
    ).all()
    lock_sql = str(
        routes._guestlist_entry_lock_query(
            added.json()["event_id"], "mint-guest"
        ).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert [row.status for row in rows].count(CheckInStatus.revoked.value) == 1
    assert [row.status for row in rows].count(CheckInStatus.issued.value) == 1
    assert "FOR UPDATE" in lock_sql
    assert "event_guestlist_entries.guest_user_id = 'mint-guest'" in lock_sql


def test_readd_locks_guest_before_revoking_tokens(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("events.users_client.notify_user", lambda *_args, **_kwargs: True)
    client = TestClient(app)
    added = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=MANAGER_HEADERS,
        json={"user_id": "readd-guest", "display_name": "Readd Guest"},
    )
    assert added.status_code == 201
    guest_headers = {**TOKEN_HEADERS, "X-Threshold-User-Id": "readd-guest"}
    minted = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers=guest_headers,
    )
    assert minted.status_code == 201
    statements: list[str] = []

    def capture_statement(
        _connection: Connection,
        _cursor: object,
        statement: str,
        _parameters: Any,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    engine = session.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", capture_statement)
    try:
        readded = client.post(
            "/v1/events/warehouse-signal/guestlist",
            headers=MANAGER_HEADERS,
            json={"user_id": "readd-guest", "display_name": "Readd Guest Again"},
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", capture_statement)

    guest_select = next(
        index
        for index, statement in enumerate(statements)
        if statement.lstrip().upper().startswith("SELECT")
        and "FROM event_guestlist_entries" in statement
    )
    token_update = next(
        index
        for index, statement in enumerate(statements)
        if statement.lstrip().upper().startswith("UPDATE EVENT_CHECK_IN_TOKENS")
    )
    lock_sql = str(
        routes._guestlist_entry_lock_query(
            added.json()["event_id"],
            "readd-guest",
            active_only=False,
        ).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    session.expire_all()
    token_row = session.scalar(
        select(EventCheckInToken).where(
            EventCheckInToken.guestlist_entry_id == added.json()["id"]
        )
    )

    assert readded.status_code == 201
    assert guest_select < token_update
    assert "FOR UPDATE" in lock_sql
    assert token_row is not None
    assert token_row.status == CheckInStatus.revoked.value


def test_mint_conflict_rolls_back_revocation_without_500(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    added = client.post(
        "/v1/events/warehouse-signal/guestlist",
        headers=MANAGER_HEADERS,
        json={"user_id": "conflict-guest", "display_name": "Conflict Guest"},
    )
    assert added.status_code == 201
    guest_headers = {**TOKEN_HEADERS, "X-Threshold-User-Id": "conflict-guest"}
    first = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers=guest_headers,
    )
    assert first.status_code == 201
    original_commit = Session.commit

    def conflict_on_token_insert(db_session: Session) -> None:
        if any(isinstance(row, EventCheckInToken) for row in db_session.new):
            raise IntegrityError("issued token conflict", {}, Exception())
        original_commit(db_session)

    monkeypatch.setattr(Session, "commit", conflict_on_token_insert)
    conflict = client.post(
        "/v1/events/warehouse-signal/guestlist/me/qr-token",
        headers=guest_headers,
    )
    session.expire_all()
    rows = session.scalars(
        select(EventCheckInToken).where(
            EventCheckInToken.guestlist_entry_id == added.json()["id"]
        )
    ).all()

    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "check-in token mint conflict"}
    assert len(rows) == 1
    assert rows[0].status == CheckInStatus.issued.value
    assert rows[0].token_hash == routes._token_hash(first.json()["token"])
