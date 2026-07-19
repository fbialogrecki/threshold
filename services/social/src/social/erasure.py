from collections.abc import Iterable

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from social.domain.models import AccountErasureTombstone

# Namespace Social locks away from other services using the same user IDs.
SOCIAL_ERASURE_LOCK_SEED = 0x534F4349414C


def fenced_erased_user_ids(session: Session, user_ids: Iterable[str | None]) -> set[str]:
    """Lock user write domains, then return IDs already durably erased.

    PostgreSQL advisory locks serialize ordinary writes with account erasure for
    the lifetime of the current transaction. SQLite serializes writes at the
    database level; tests still use the same sorted/deduplicated tombstone check.
    """
    ordered_ids = sorted({user_id.strip() for user_id in user_ids if user_id and user_id.strip()})
    if not ordered_ids:
        return set()

    if session.get_bind().dialect.name == "postgresql":
        lock_statement = text(
            "SELECT pg_advisory_xact_lock(hashtextextended(:id, :seed))"
        )
        for user_id in ordered_ids:
            session.execute(
                lock_statement,
                {"id": user_id, "seed": SOCIAL_ERASURE_LOCK_SEED},
            )

    # Keep this separate from advisory-lock statements: lock acquisition must
    # complete for every ID before any tombstone decision is made.
    return set(
        session.scalars(
            select(AccountErasureTombstone.user_id).where(
                AccountErasureTombstone.user_id.in_(ordered_ids)
            )
        ).all()
    )
