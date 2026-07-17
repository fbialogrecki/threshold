from sqlalchemy import text
from sqlalchemy.engine import Engine


def check_database_ready(engine: Engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
