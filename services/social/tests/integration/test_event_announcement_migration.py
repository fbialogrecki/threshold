from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _migration(filename: str) -> Any:
    path = Path(__file__).parents[2] / f"migrations/versions/{filename}.py"
    spec = spec_from_file_location(filename, path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_event_announcement_upgrade_path_and_downgrade_on_sqlite() -> None:
    migrations = [
        _migration("0009_event_announcements"),
        _migration("0010_post_event_slug"),
        _migration("0011_post_event_id"),
        _migration("0012_event_announcement_indexes"),
    ]
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table(
        "posts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("media_asset_ids", sa.JSON(), nullable=False),
    )
    sa.Table("groups", metadata, sa.Column("id", sa.String(36), primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migrations[0].upgrade()
        assert {
            index["name"]
            for index in sa.inspect(connection).get_indexes("event_announcements")
        } == {"ix_event_announcements_post_id"}

        with Operations.context(context):
            for migration in migrations[1:]:
                migration.upgrade()

        assert {
            index["name"]
            for index in sa.inspect(connection).get_indexes("event_announcements")
        } == {
            "ix_event_announcements_event_slug",
            "ix_event_announcements_post_created",
        }
        assert {
            index["name"] for index in sa.inspect(connection).get_indexes("posts")
        } == {"ix_posts_event_id", "ix_posts_event_slug"}
        assert {
            constraint["name"]
            for constraint in sa.inspect(connection).get_check_constraints("posts")
        } == {"ck_posts_event_reference_pair", "ck_posts_image_or_event"}

        with Operations.context(context):
            migrations[3].downgrade()
        assert {
            index["name"]
            for index in sa.inspect(connection).get_indexes("event_announcements")
        } == {"ix_event_announcements_post_id"}

        with Operations.context(context):
            for migration in reversed(migrations[:3]):
                migration.downgrade()
        assert "event_announcements" not in sa.inspect(connection).get_table_names()
        assert {"event_id", "event_slug"}.isdisjoint(
            column["name"] for column in sa.inspect(connection).get_columns("posts")
        )


def test_event_announcement_forward_indexes_emit_postgresql_sql() -> None:
    migration = _migration("0012_event_announcement_indexes")
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )

    with Operations.context(context):
        migration.upgrade()
        migration.downgrade()

    sql = output.getvalue().lower()
    assert "drop index ix_event_announcements_post_id" in sql
    assert "create index ix_event_announcements_event_slug" in sql
    assert "create index ix_event_announcements_post_created" in sql
    assert "drop index ix_event_announcements_event_slug" in sql
    assert "drop index ix_event_announcements_post_created" in sql
    assert "create index ix_event_announcements_post_id" in sql
