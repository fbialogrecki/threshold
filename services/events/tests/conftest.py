from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from events.api.security import reset_write_quota_for_tests
from events.db.base import Base
from events.domain.models import Event
from events.main_dependencies import override_database, settings
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from events import users_client

PAGE_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True)
def configure_test_settings() -> None:
    settings.threshold_internal_token = "test-internal-token"
    settings.media_service_url = None
    settings.media_request_timeout_seconds = 1.5
    settings.write_rate_limit_count = 60
    settings.write_rate_limit_window_seconds = 60
    reset_write_quota_for_tests()


@pytest.fixture(autouse=True)
def mock_users_client(monkeypatch: pytest.MonkeyPatch) -> None:
    def _check_page_role(_settings: object, _page_id: str, _user_id: str) -> str | None:
        return "admin"

    monkeypatch.setattr(users_client, "check_page_role", _check_page_role)


@pytest.fixture()
def session() -> Generator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

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
        Event(
            slug="warehouse-signal",
            title="Warehouse Signal",
            starts_at=datetime(2026, 7, 1, 22, 0, tzinfo=UTC),
            city="Warsaw",
            page_id=PAGE_ID,
            created_by_user_id="user-1",
            genres=["techno"],
        )
    )
    db_session.commit()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
