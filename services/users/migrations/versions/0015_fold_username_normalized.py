"""recompute username_normalized with diacritic folding

Usernames are now the only public name for a person, so uniqueness has to be
stricter than a case fold: `Żaba` and `Zaba` differ by one ogonek and must not
both exist. `username_normalized` therefore folds diacritics as well as case.

The unique index means folding can make two existing accounts collide. This
migration refuses to guess a winner: it reports the conflicting pairs and stops,
so a human decides who renames.

Revision ID: 0015_fold_username_normalized
Revises: 0014_account_erasure_jobs
Create Date: 2026-07-24
"""

import unicodedata
from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_fold_username_normalized"
down_revision: str | None = "0014_account_erasure_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kept local rather than imported from the service: a migration has to keep
# meaning the same thing even after the application's rules move on.
_EXPLICIT_FOLD = str.maketrans({"ł": "l", "Ł": "l"})


def _fold(username: str) -> str:
    lowered = username.strip().lower().translate(_EXPLICIT_FOLD)
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, username FROM application_users "
            "WHERE username IS NOT NULL AND status <> 'deleted'"
        )
    ).fetchall()

    folded: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        folded[_fold(row.username)].append(row.username)

    collisions = {key: names for key, names in folded.items() if len(names) > 1}
    if collisions:
        detail = "; ".join(
            f"{key}: {', '.join(sorted(names))}" for key, names in collisions.items()
        )
        raise RuntimeError(
            "Folding usernames would violate uq_application_users_username_normalized. "
            f"Resolve these accounts before migrating — {detail}"
        )

    for row in rows:
        connection.execute(
            sa.text("UPDATE application_users SET username_normalized = :norm WHERE id = :id"),
            {"norm": _fold(row.username), "id": row.id},
        )


def downgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, username FROM application_users WHERE username IS NOT NULL")
    ).fetchall()
    for row in rows:
        connection.execute(
            sa.text("UPDATE application_users SET username_normalized = :norm WHERE id = :id"),
            {"norm": row.username.strip().lower(), "id": row.id},
        )
