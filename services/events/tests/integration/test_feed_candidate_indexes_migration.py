from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _migration() -> Any:
    path = Path(__file__).parents[2] / "migrations/versions/0007_feed_candidate_indexes.py"
    spec = spec_from_file_location("feed_candidate_indexes_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_feed_candidate_indexes_upgrade_and_downgrade_on_sqlite() -> None:
    migration = _migration()
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table(
        "events",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        indexes = {
            row[1]
            for row in connection.execute(sa.text("PRAGMA index_list('events')")).all()
            if row[1].startswith("ix_events_")
        }
        assert indexes == {
            "ix_events_city_lower",
            "ix_events_created_by_user_id",
            "ix_events_created_cursor",
        }
        city_index_sql = connection.scalar(
            sa.text(
                """
                SELECT sql
                FROM sqlite_master
                WHERE type = 'index' AND name = 'ix_events_city_lower'
                """
            )
        )
        assert city_index_sql is not None
        assert "lower(city)" in city_index_sql.lower()

        with Operations.context(context):
            migration.downgrade()
        assert not {
            row[1]
            for row in connection.execute(sa.text("PRAGMA index_list('events')")).all()
            if row[1].startswith("ix_events_")
        }


def test_feed_candidate_indexes_emit_postgresql_sql() -> None:
    migration = _migration()
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )

    with Operations.context(context):
        migration.upgrade()
        migration.downgrade()

    sql = output.getvalue().lower()
    assert "create index ix_events_city_lower on events (lower(city))" in sql
    assert "create index ix_events_created_by_user_id" in sql
    assert "create index ix_events_created_cursor" in sql
    assert "drop index ix_events_city_lower" in sql
    assert "drop index ix_events_created_by_user_id" in sql
    assert "drop index ix_events_created_cursor" in sql
