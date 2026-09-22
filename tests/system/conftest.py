"""Independent from service conftests: real processes, no dependency overrides."""

from collections.abc import Iterator

import pytest

from .harness import Stack


@pytest.fixture(scope="session")
def database_stack() -> Iterator[Stack]:
    with Stack() as stack:
        stack.prepare_databases()
        yield stack


@pytest.fixture(scope="session")
def http_stack(database_stack: Stack) -> Iterator[Stack]:
    assert hasattr(database_stack, "start_services"), "real HTTP process harness is not implemented"
    database_stack.start_services()
    yield database_stack
