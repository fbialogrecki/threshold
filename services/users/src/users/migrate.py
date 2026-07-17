from pathlib import Path

from alembic import command
from alembic.config import Config

from users.settings import Settings

SERVICE_DIR = Path(__file__).resolve().parents[2]


def run_migrations() -> None:
    settings = Settings()
    config = Config(str(SERVICE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


if __name__ == "__main__":
    run_migrations()
