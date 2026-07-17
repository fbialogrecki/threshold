from collections.abc import Generator

import pytest
from social.api.security import reset_write_quota_for_tests
from social.db.base import Base
from social.domain.models import Group
from social.main_dependencies import override_database, settings
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def configure_test_settings() -> None:
    settings.threshold_internal_token = "test-internal-token"
    settings.media_service_url = None
    settings.media_request_timeout_seconds = 1.5
    settings.nats_enabled = False
    settings.write_rate_limit_count = 60
    settings.write_rate_limit_window_seconds = 60
    reset_write_quota_for_tests()


@pytest.fixture()
def session() -> Generator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite ignores FK cascades unless enabled; Postgres enforces them always.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    override_database(engine, factory)
    db_session = factory()
    db_session.add(
        Group(
            slug="techno-warsaw",
            name="Techno Warsaw",
            city="Warsaw",
            scene_tag="techno",
            official=True,
        )
    )
    db_session.commit()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
