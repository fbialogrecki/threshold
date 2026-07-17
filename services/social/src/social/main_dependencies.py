from collections.abc import Generator

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from social.db.base import Base, build_engine, session_scope
from social.settings import Settings

settings = Settings()
engine = build_engine(settings.database_url)
session_factory = sessionmaker(bind=engine, expire_on_commit=False)


def create_schema_for_local_sqlite() -> None:
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


def get_db_session() -> Generator[Session]:
    yield from session_scope(session_factory)


def override_database(test_engine: Engine, factory: sessionmaker[Session]) -> None:
    global engine, session_factory
    engine = test_engine
    session_factory = factory
