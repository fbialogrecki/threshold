from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _migration() -> ModuleType:
    path = Path(__file__).parents[2] / "migrations/versions/0013_erasure_tombstones.py"
    spec = spec_from_file_location("social_erasure_tombstone_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_erasure_tombstone_migration_upgrade_and_downgrade_on_sqlite() -> None:
    migration = _migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        inspector = sa.inspect(connection)
        assert "account_erasure_tombstones" in inspector.get_table_names()
        columns = {
            column["name"]: column
            for column in inspector.get_columns("account_erasure_tombstones")
        }
        assert set(columns) == {"user_id", "erased_at"}
        assert columns["user_id"]["nullable"] is False
        assert columns["erased_at"]["nullable"] is False
        assert inspector.get_pk_constraint("account_erasure_tombstones")["constrained_columns"] == [
            "user_id"
        ]

        with Operations.context(context):
            migration.downgrade()
        assert "account_erasure_tombstones" not in sa.inspect(connection).get_table_names()
