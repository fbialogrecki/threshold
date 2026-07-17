from collections.abc import Generator

import pytest
from media.db.base import Base
from media.main_dependencies import override_database, override_object_storage, settings
from media.storage import InMemoryObjectStorage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def configure_test_settings() -> None:
    settings.threshold_internal_token = "test-internal-token"
    settings.s3_endpoint_url = "http://127.0.0.1:8333"
    settings.s3_bucket = "threshold-media"
    settings.s3_region = "us-east-1"
    settings.s3_path_style = True
    settings.max_image_bytes = 10_000_000
    settings.max_upload_bytes = 10_100_000
    settings.upload_temp_dir = None


@pytest.fixture()
def object_storage() -> Generator[InMemoryObjectStorage]:
    storage = InMemoryObjectStorage()
    override_object_storage(storage)
    try:
        yield storage
    finally:
        override_object_storage(None)


@pytest.fixture()
def session() -> Generator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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
