from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_post_event_id_migration_backfills_deterministically_and_downgrades() -> None:
    path = Path(__file__).parents[2] / "migrations/versions/0011_post_event_id.py"
    spec = spec_from_file_location("post_event_id_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    posts = sa.Table(
        "posts",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_slug", sa.String(160), nullable=True),
        sa.Column("media_asset_ids", sa.JSON(), nullable=False),
    )
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
        connection.execute(
            posts.insert(),
            [
                {"id": "ordinary", "event_slug": None, "media_asset_ids": []},
                {
                    "id": "announcement",
                    "event_slug": "stale-slug",
                    "media_asset_ids": [],
                },
            ],
        )
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
        assert columns["event_id"]["nullable"] is True
        assert columns["event_id"]["type"].length == 36
        assert connection.execute(
            sa.text("SELECT id, event_id, event_slug FROM posts ORDER BY id")
        ).all() == [
            ("announcement", "event-z", "zebra-night"),
            ("ordinary", None, None),
        ]
        assert "ix_posts_event_id" in {
            index["name"] for index in sa.inspect(connection).get_indexes("posts")
        }
        assert {
            constraint["name"]
            for constraint in sa.inspect(connection).get_check_constraints("posts")
        } == {"ck_posts_event_reference_pair", "ck_posts_image_or_event"}

        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO posts (id, event_id, event_slug, media_asset_ids)
                    VALUES ('only-id', 'event-only', NULL, '[]')
                    """
                )
            )
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO posts (id, event_id, event_slug, media_asset_ids)
                    VALUES ('image-event', 'event-image', 'image-event', '["asset"]')
                    """
                )
            )

        with Operations.context(context):
            migration.downgrade()
        assert "event_id" not in {
            column["name"] for column in sa.inspect(connection).get_columns("posts")
        }


def test_post_event_id_migration_emits_portable_postgresql_sql() -> None:
    path = Path(__file__).parents[2] / "migrations/versions/0011_post_event_id.py"
    spec = spec_from_file_location("post_event_id_postgresql_migration", path)
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
    assert "set (event_id, event_slug)" in sql
    assert "order by event_announcements.created_at, event_announcements.id" in sql
    assert "constraint ck_posts_event_reference_pair" in sql
    assert "constraint ck_posts_image_or_event" in sql
    assert "drop constraint ck_posts_event_reference_pair" in sql
    assert "drop constraint ck_posts_image_or_event" in sql
