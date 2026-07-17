from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


def test_event_door_staff_migration_constraints_cascade_and_downgrade() -> None:
    path = Path(__file__).parents[2] / "migrations/versions/0005_event_door_staff.py"
    spec = spec_from_file_location("event_door_staff_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    metadata = sa.MetaData()
    events = sa.Table("events", metadata, sa.Column("id", sa.String(36), primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        inspector = sa.inspect(connection)
        assert {column["name"] for column in inspector.get_columns("event_door_staff")} == {
            "id",
            "event_id",
            "user_id",
            "assigned_by_user_id",
            "assigned_at",
            "updated_at",
        }
        assert {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("event_door_staff")
        } == {"uq_event_door_staff_event_user"}
        foreign_key = inspector.get_foreign_keys("event_door_staff")[0]
        assert foreign_key["referred_table"] == "events"
        assert foreign_key["options"]["ondelete"] == "CASCADE"
        assert {index["name"] for index in inspector.get_indexes("event_door_staff")} == {
            "ix_event_door_staff_user"
        }

        connection.execute(events.insert().values(id="event-1"))
        assigned_at = datetime(2026, 7, 10, tzinfo=UTC)
        row = {
            "id": "door-1",
            "event_id": "event-1",
            "user_id": "user-1",
            "assigned_by_user_id": "manager-1",
            "assigned_at": assigned_at,
            "updated_at": assigned_at,
        }
        connection.execute(sa.text(
            """
            INSERT INTO event_door_staff
                (id, event_id, user_id, assigned_by_user_id, assigned_at, updated_at)
            VALUES
                (:id, :event_id, :user_id, :assigned_by_user_id, :assigned_at, :updated_at)
            """
        ), row)
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO event_door_staff
                        (id, event_id, user_id, assigned_by_user_id, assigned_at, updated_at)
                    VALUES
                        ('door-2', :event_id, :user_id, :assigned_by_user_id,
                         :assigned_at, :updated_at)
                    """
                ),
                row,
            )

        connection.execute(events.delete().where(events.c.id == "event-1"))
        assert connection.scalar(sa.text("SELECT count(*) FROM event_door_staff")) == 0

        with Operations.context(context):
            migration.downgrade()
        assert "event_door_staff" not in sa.inspect(connection).get_table_names()
