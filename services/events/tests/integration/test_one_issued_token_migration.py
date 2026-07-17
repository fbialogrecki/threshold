from datetime import UTC, datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


def _migration() -> ModuleType:
    path = Path(__file__).parents[2] / "migrations/versions/0006_one_issued_check_in_token.py"
    spec = spec_from_file_location("one_issued_check_in_token_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_one_issued_token_migration_reconciles_and_downgrades_on_sqlite() -> None:
    migration = _migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    tokens = sa.Table(
        "event_check_in_tokens",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("guestlist_entry_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)
    now = datetime(2026, 7, 10, tzinfo=UTC)

    with engine.begin() as connection:
        connection.execute(
            tokens.insert(),
            [
                {
                    "id": "old",
                    "guestlist_entry_id": "entry-a",
                    "status": "issued",
                    "created_at": now - timedelta(minutes=1),
                },
                {
                    "id": "new-a",
                    "guestlist_entry_id": "entry-a",
                    "status": "issued",
                    "created_at": now,
                },
                {
                    "id": "new-z",
                    "guestlist_entry_id": "entry-a",
                    "status": "issued",
                    "created_at": now,
                },
                {
                    "id": "used",
                    "guestlist_entry_id": "entry-a",
                    "status": "used",
                    "created_at": now + timedelta(minutes=1),
                },
                {
                    "id": "only",
                    "guestlist_entry_id": "entry-b",
                    "status": "issued",
                    "created_at": now,
                },
            ],
        )
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        rows = connection.execute(
            sa.text(
                "SELECT id, status FROM event_check_in_tokens "
                "ORDER BY guestlist_entry_id, id"
            )
        ).all()
        assert rows == [
            ("new-a", "revoked"),
            ("new-z", "issued"),
            ("old", "revoked"),
            ("used", "used"),
            ("only", "issued"),
        ]
        index_sql = connection.scalar(
            sa.text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'index' "
                "AND name = 'uq_event_check_in_tokens_one_issued'"
            )
        )
        assert index_sql is not None
        assert "UNIQUE INDEX" in index_sql
        assert "WHERE status = 'issued'" in index_sql
        with pytest.raises(IntegrityError):
            connection.execute(
                tokens.insert().values(
                    id="duplicate",
                    guestlist_entry_id="entry-a",
                    status="issued",
                    created_at=now + timedelta(minutes=2),
                )
            )

        with Operations.context(context):
            migration.downgrade()
        assert "uq_event_check_in_tokens_one_issued" not in {
            index["name"] for index in sa.inspect(connection).get_indexes(tokens.name)
        }
        connection.execute(
            tokens.insert().values(
                id="after-downgrade",
                guestlist_entry_id="entry-a",
                status="issued",
                created_at=now + timedelta(minutes=3),
            )
        )


def test_one_issued_token_migration_emits_postgresql_partial_index() -> None:
    migration = _migration()
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )

    with Operations.context(context):
        migration.upgrade()

    sql = output.getvalue()
    lock_position = sql.index(
        "LOCK TABLE event_check_in_tokens IN SHARE ROW EXCLUSIVE MODE"
    )
    cleanup_position = sql.index("UPDATE event_check_in_tokens")
    index_position = sql.index(
        "CREATE UNIQUE INDEX uq_event_check_in_tokens_one_issued"
    )
    assert lock_position < cleanup_position < index_position
    assert "row_number() OVER" in sql
    assert (
        "CREATE UNIQUE INDEX uq_event_check_in_tokens_one_issued "
        "ON event_check_in_tokens (guestlist_entry_id) WHERE status = 'issued'"
    ) in sql
