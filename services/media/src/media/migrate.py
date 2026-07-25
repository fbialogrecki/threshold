import logging

from alembic import command
from alembic.config import Config

# Package-relative so the same string resolves in the source tree and in the
# installed wheel, where the service directory no longer exists.
SCRIPT_LOCATION = "media:migrations"


def build_config() -> Config:
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    return config


def run_migrations() -> None:
    # alembic.ini is not read here, so its logger levels are reproduced by hand:
    # the upgrade log is the only record a finished migration Job leaves behind.
    logging.basicConfig(format="%(levelname)-5.5s [%(name)s] %(message)s", level=logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)
    command.upgrade(build_config(), "head")


if __name__ == "__main__":
    run_migrations()
