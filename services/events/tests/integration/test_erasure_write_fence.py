from typing import Any, cast

import pytest
from events.erasure_write_fence import (
    EVENTS_ERASURE_LOCK_SEED,
    enforce_account_erasure_write_fence,
)
from fastapi import HTTPException
from sqlalchemy.orm import Session


class _Dialect:
    name = "postgresql"


class _Bind:
    dialect = _Dialect()


class _Scalars:
    def all(self) -> list[str]:
        return []


class _RecordingSession:
    bind = _Bind()

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def get_bind(self) -> _Bind:
        return self.bind

    def execute(self, statement: object, parameters: dict[str, object]) -> None:
        self.calls.append((str(statement), parameters))

    def scalars(self, statement: object) -> _Scalars:
        self.calls.append((str(statement), None))
        return _Scalars()


def test_postgresql_fence_sorts_deduplicates_locks_then_queries() -> None:
    session = _RecordingSession()

    enforce_account_erasure_write_fence(
        cast(Session, cast(Any, session)),
        ["user-b", "user-a", "user-b", ""],
    )

    assert [parameters for _, parameters in session.calls] == [
        {"user_id": "user-a", "seed": EVENTS_ERASURE_LOCK_SEED},
        {"user_id": "user-b", "seed": EVENTS_ERASURE_LOCK_SEED},
        None,
    ]
    assert all(
        "pg_advisory_xact_lock(hashtextextended(:user_id, :seed))" in sql
        for sql, _ in session.calls[:2]
    )
    assert "account_erasure_tombstones" in session.calls[2][0]


def test_sqlite_fence_rejects_tombstoned_id(session: Session) -> None:
    from events.domain.models import AccountErasureTombstone

    session.add(AccountErasureTombstone(user_id="erased-user"))
    session.commit()

    with pytest.raises(HTTPException) as exc_info:
        enforce_account_erasure_write_fence(session, ["active-user", "erased-user"])

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "account has been erased"