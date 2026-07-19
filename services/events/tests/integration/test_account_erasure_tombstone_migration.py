from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _migration() -> Any:
    path = Path(__file__).parents[2] / "migrations/versions/0008_account_erasure_tombstones.py"
    spec = spec_from_file_location("account_erasure_tombstones_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_account_erasure_tombstone_upgrade_and_downgrade_on_sqlite() -> None:
    migration = _migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        columns = {
            row[1]: {"type": row[2], "nullable": not bool(row[3]), "primary_key": bool(row[5])}
            for row in connection.execute(
                sa.text("PRAGMA table_info('account_erasure_tombstones')")
            ).all()
        }
        assert columns == {
            "user_id": {"type": "VARCHAR(36)", "nullable": False, "primary_key": True},
            "erased_at": {"type": "DATETIME", "nullable": False, "primary_key": False},
        }

        connection.execute(
            sa.text(
                "INSERT INTO account_erasure_tombstones (user_id, erased_at) "
                "VALUES ('user-1', '2026-07-19T00:00:00Z')"
            )
        )
        with Operations.context(context):
            migration.downgrade()
        tables = sa.inspect(connection).get_table_names()
        assert "account_erasure_tombstones" not in tables
