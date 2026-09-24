"""Periodic repair of social's copy of user blocks from the canonical users service.

Block changes normally arrive as NATS events, but NATS Core does not guarantee
delivery. A lost event would leave a block unenforced here indefinitely, so
this loop regularly replaces the local copy with the users service's list.
"""

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from social.domain.models import UserBlock, utc_now
from social.erasure import fenced_erased_user_ids
from social.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanonicalBlock:
    blocker_user_id: str
    blocker_username: str | None
    blocked_user_id: str
    blocked_username: str | None


async def fetch_canonical_blocks(settings: Settings) -> list[CanonicalBlock]:
    if not settings.users_service_url or not settings.threshold_internal_token:
        raise RuntimeError("users service URL or internal token is not configured")
    async with httpx.AsyncClient(timeout=settings.block_sync_timeout_seconds) as client:
        response = await client.get(
            f"{settings.users_service_url.rstrip('/')}/internal/v1/blocks",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token},
        )
        response.raise_for_status()
        payload: Any = response.json()
    if not isinstance(payload, list):
        raise ValueError("users blocks response is not a list")
    return [
        CanonicalBlock(
            blocker_user_id=str(item["blocker_user_id"]),
            blocker_username=item.get("blocker_username"),
            blocked_user_id=str(item["blocked_user_id"]),
            blocked_username=item.get("blocked_username"),
        )
        for item in payload
    ]


def _as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes even for timezone-aware columns.
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def reconcile_user_blocks(
    session: Session, canonical: Iterable[CanonicalBlock], *, fetched_at: datetime
) -> tuple[int, int]:
    """Make the local table match `canonical`. Returns (added, removed).

    Rows created after `fetched_at` came from a NATS event newer than the
    snapshot and are kept; the next run will see them in the users service.
    """
    wanted = {(block.blocker_user_id, block.blocked_user_id): block for block in canonical}
    erased = fenced_erased_user_ids(session, [user_id for pair in wanted for user_id in pair])
    existing = {
        (row.blocker_user_id, row.blocked_user_id): row
        for row in session.scalars(select(UserBlock)).all()
    }

    added = removed = 0
    for pair, block in wanted.items():
        if erased.intersection(pair):
            continue
        row = existing.get(pair)
        if row is None:
            session.add(
                UserBlock(
                    blocker_user_id=block.blocker_user_id,
                    blocker_username=block.blocker_username,
                    blocked_user_id=block.blocked_user_id,
                    blocked_username=block.blocked_username,
                )
            )
            added += 1
        else:
            row.blocker_username = block.blocker_username
            row.blocked_username = block.blocked_username
    for pair, row in existing.items():
        if pair not in wanted and _as_utc(row.created_at) < fetched_at:
            session.delete(row)
            removed += 1
    return added, removed


async def sync_blocks_once(settings: Settings, session_factory: sessionmaker[Session]) -> None:
    fetched_at = utc_now()
    canonical = await fetch_canonical_blocks(settings)

    def _apply() -> tuple[int, int]:
        with session_factory() as session:
            result = reconcile_user_blocks(session, canonical, fetched_at=fetched_at)
            session.commit()
            return result

    added, removed = await asyncio.to_thread(_apply)
    if added or removed:
        logger.warning(
            "repaired social block copy from users",
            extra={"blocks_added": added, "blocks_removed": removed},
        )


async def run_block_sync_loop(settings: Settings, session_factory: sessionmaker[Session]) -> None:
    while True:
        try:
            await sync_blocks_once(settings, session_factory)
        except Exception:
            logger.exception("social block sync failed; retrying next interval")
        await asyncio.sleep(settings.block_sync_interval_seconds)
