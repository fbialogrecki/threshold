"""Real PostgreSQL migrations and least-privilege checks."""

from .test_resource_fence import harness_module


def test_empty_and_predecessor_migrations_with_separate_runtime_roles() -> None:
    harness = harness_module()
    assert hasattr(harness, "Stack"), "disposable PostgreSQL stack is not implemented"
    with harness.Stack() as stack:
        stack.prepare_databases()
        assert stack.migration_paths == {"users": {"empty", "predecessor"},
                                         "social": {"empty", "predecessor"}}
        stack.verify_runtime_roles()
