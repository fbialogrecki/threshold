from collections.abc import Generator

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from media.db.base import Base, build_engine, build_session_factory, session_scope
from media.settings import Settings
from media.storage import ObjectStorage, S3ObjectStorage

settings = Settings()
engine = build_engine(settings.database_url)
SessionFactory = build_session_factory(settings.database_url)
_storage: ObjectStorage | None = None


def create_schema_for_local_sqlite() -> None:
    if settings.database_url == "sqlite+pysqlite:///:memory:":
        import media.domain.models  # noqa: F401

        Base.metadata.create_all(bind=engine)


def get_session() -> Generator[Session]:
    yield from session_scope(SessionFactory)


def get_object_storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        _storage = S3ObjectStorage(settings)
    return _storage


def override_object_storage(storage: ObjectStorage | None) -> None:
    global _storage
    _storage = storage


def override_database(new_engine: Engine, new_factory: sessionmaker[Session]) -> None:
    global engine, SessionFactory
    engine = new_engine
    SessionFactory = new_factory
