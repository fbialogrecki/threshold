from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from users.api.routes import reset_auth_rate_limits_for_tests
from users.db.base import Base
from users.main_dependencies import override_database, settings


@pytest.fixture(autouse=True)
def configure_test_settings() -> None:
    settings.auth_dev_expose_tokens = True
    settings.threshold_internal_token = "test-internal-token"
    settings.auth_rate_limit_count = 120
    settings.auth_rate_limit_window_seconds = 60
    settings.account_erasure_worker_enabled = False
    reset_auth_rate_limits_for_tests()


@pytest.fixture()
def session(tmp_path: Path) -> Generator[Session]:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'users.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    override_database(engine, factory)
    db_session = factory()
    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
