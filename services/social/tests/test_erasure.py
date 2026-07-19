from typing import Any, cast

from social.erasure import SOCIAL_ERASURE_LOCK_SEED, fenced_erased_user_ids
from sqlalchemy.orm import Session


class _Rows:
    def __init__(self, values: list[str]) -> None:
        self.values = values

    def all(self) -> list[str]:
        return self.values


class _FakeSession:
    def __init__(self, dialect_name: str, erased: list[str]) -> None:
        self.bind = type("Bind", (), {"dialect": type("Dialect", (), {"name": dialect_name})()})()
        self.erased = erased
        self.operations: list[tuple[str, Any, Any]] = []

    def get_bind(self) -> Any:
        return self.bind

    def execute(self, statement: Any, parameters: Any) -> None:
        self.operations.append(("execute", statement, parameters))

    def scalars(self, statement: Any) -> _Rows:
        self.operations.append(("scalars", statement, None))
        return _Rows(self.erased)


def test_postgresql_fence_sorts_deduplicates_locks_then_queries_tombstones() -> None:
    fake = _FakeSession("postgresql", ["user-z"])

    erased = fenced_erased_user_ids(
        cast(Session, fake), ["user-z", "user-a", "user-z", None, " "]
    )

    assert erased == {"user-z"}
    assert [operation[0] for operation in fake.operations] == ["execute", "execute", "scalars"]
    assert [operation[2] for operation in fake.operations[:2]] == [
        {"id": "user-a", "seed": SOCIAL_ERASURE_LOCK_SEED},
        {"id": "user-z", "seed": SOCIAL_ERASURE_LOCK_SEED},
    ]
    assert all(
        "pg_advisory_xact_lock(hashtextextended" in str(operation[1])
        for operation in fake.operations[:2]
    )


def test_sqlite_fence_uses_deterministic_tombstone_query_without_postgres_sql() -> None:
    fake = _FakeSession("sqlite", ["user-a"])

    erased = fenced_erased_user_ids(cast(Session, fake), ["user-z", "user-a", "user-z"])

    assert erased == {"user-a"}
    assert [operation[0] for operation in fake.operations] == ["scalars"]
    compiled = fake.operations[0][1].compile()
    assert compiled.params == {"user_id_1": ["user-a", "user-z"]}
