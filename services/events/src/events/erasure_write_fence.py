from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from events.domain.models import AccountErasureTombstone

# Namespace Events locks away from other services fencing the same user IDs.
EVENTS_ERASURE_LOCK_SEED = 0x4556454E5453


def acquire_account_erasure_write_fence(
    session: Session,
    user_ids: Iterable[str | None],
) -> set[str]:
    """Serialize user-linked writes with erasure and return erased IDs."""
    normalized_ids = sorted({user_id for user_id in user_ids if user_id})
    if not normalized_ids:
        return set()

    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        lock_statement = text(
            "SELECT pg_advisory_xact_lock(hashtextextended(:user_id, :seed))"
        )
        for user_id in normalized_ids:
            session.execute(
                lock_statement,
                {"user_id": user_id, "seed": EVENTS_ERASURE_LOCK_SEED},
            )

    return set(
        session.scalars(
            select(AccountErasureTombstone.user_id).where(
                AccountErasureTombstone.user_id.in_(normalized_ids)
            )
        ).all()
    )


def enforce_account_erasure_write_fence(
    session: Session,
    user_ids: Iterable[str | None],
) -> None:
    """Serialize user-linked writes with erasure and reject erased IDs."""
    if acquire_account_erasure_write_fence(session, user_ids):
        raise HTTPException(status_code=409, detail="account has been erased")