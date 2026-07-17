from sqlalchemy import text
from sqlalchemy.engine import Engine


def check_database_ready(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("select 1"))
        if not engine.url.drivername.startswith("sqlite"):
            connection.execute(text("select 1 from alembic_version"))
