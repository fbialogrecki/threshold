from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_post_event_slug_migration_adds_nullable_column_and_backfills_announcements() -> None:
    path = Path(__file__).parents[2] / "migrations/versions/0010_post_event_slug.py"
    spec = spec_from_file_location("post_event_slug_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    posts = sa.Table("posts", metadata, sa.Column("id", sa.String(36), primary_key=True))
    announcements = sa.Table(
        "event_announcements",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("post_id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("event_slug", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(posts.insert(), [{"id": "ordinary"}, {"id": "announcement"}])
        connection.execute(
            announcements.insert(),
            [
                {
                    "id": "row-z",
                    "post_id": "announcement",
                    "event_id": "event-z",
                    "event_slug": "zebra-night",
                    "created_at": datetime(2026, 7, 1, tzinfo=UTC),
                },
                {
                    "id": "row-a",
                    "post_id": "announcement",
                    "event_id": "event-a",
                    "event_slug": "warehouse-signal",
                    "created_at": datetime(2026, 7, 2, tzinfo=UTC),
                },
            ],
        )
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        columns = {column["name"]: column for column in sa.inspect(connection).get_columns("posts")}
        assert columns["event_slug"]["nullable"] is True
        assert columns["event_slug"]["type"].length == 160
        rows = connection.execute(
            sa.text("SELECT id, event_slug FROM posts ORDER BY id")
        ).all()
        assert rows == [("announcement", "zebra-night"), ("ordinary", None)]
        assert "ix_posts_event_slug" in {
            index["name"] for index in sa.inspect(connection).get_indexes("posts")
        }

        with Operations.context(context):
            migration.downgrade()
        assert "event_slug" not in {
            column["name"] for column in sa.inspect(connection).get_columns("posts")
        }


def test_post_event_slug_migration_emits_portable_postgresql_sql() -> None:
    path = Path(__file__).parents[2] / "migrations/versions/0010_post_event_slug.py"
    spec = spec_from_file_location("post_event_slug_postgresql_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )

    with Operations.context(context):
        migration.upgrade()
        migration.downgrade()

    sql = output.getvalue().lower()
    assert "order by event_announcements.created_at, event_announcements.id" in sql
    assert "create index ix_posts_event_slug" in sql
    assert "drop index ix_posts_event_slug" in sql
