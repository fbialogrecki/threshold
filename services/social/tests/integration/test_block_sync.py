import asyncio
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from social.block_sync import CanonicalBlock, reconcile_user_blocks, sync_blocks_once
from social.domain.models import UserBlock, utc_now
from social.main import app
from social.main_dependencies import settings
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from social import block_sync


def _pairs(session: Session) -> set[tuple[str, str, str | None]]:
    return {
        (row.blocker_user_id, row.blocked_user_id, row.blocked_username)
        for row in session.scalars(select(UserBlock)).all()
    }


def _canonical(blocker: str, blocked: str, blocked_username: str | None = None) -> CanonicalBlock:
    return CanonicalBlock(
        blocker_user_id=blocker,
        blocker_username=blocker,
        blocked_user_id=blocked,
        blocked_username=blocked_username or blocked,
    )


def test_reconcile_adds_missing_removes_stale_and_refreshes_usernames(session: Session) -> None:
    session.add_all(
        [
            UserBlock(blocker_user_id="a", blocked_user_id="b", blocked_username="old-b"),
            UserBlock(blocker_user_id="a", blocked_user_id="stale"),
        ]
    )
    session.commit()

    added, removed = reconcile_user_blocks(
        session,
        [_canonical("a", "b", "new-b"), _canonical("c", "d")],
        fetched_at=utc_now() + timedelta(seconds=1),
    )
    session.commit()

    assert (added, removed) == (1, 1)
    assert _pairs(session) == {("a", "b", "new-b"), ("c", "d", "d")}


def test_reconcile_keeps_blocks_newer_than_the_snapshot(session: Session) -> None:
    # A block that arrived over NATS after the users list was fetched must survive.
    fetched_at = utc_now() - timedelta(seconds=5)
    session.add(UserBlock(blocker_user_id="a", blocked_user_id="fresh"))
    session.commit()

    added, removed = reconcile_user_blocks(session, [], fetched_at=fetched_at)
    session.commit()

    assert (added, removed) == (0, 0)
    assert _pairs(session) == {("a", "fresh", None)}


def test_reconcile_does_not_recreate_blocks_for_erased_users(session: Session) -> None:
    erased = TestClient(app).post(
        "/v1/internal/anonymize-author",
        headers={"X-Threshold-Internal-Token": "test-internal-token"},
        json={"user_id": "erased-user"},
    )
    assert erased.status_code == 200

    reconcile_user_blocks(
        session, [_canonical("erased-user", "b"), _canonical("a", "b")], fetched_at=utc_now()
    )
    session.commit()

    assert _pairs(session) == {("a", "b", "b")}


def test_sync_blocks_once_applies_the_users_service_list(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_fetch(_settings: object) -> list[CanonicalBlock]:
        return [_canonical("a", "b")]

    monkeypatch.setattr(block_sync, "fetch_canonical_blocks", fake_fetch)
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)

    asyncio.run(sync_blocks_once(settings, factory))

    assert _pairs(session) == {("a", "b", "b")}
