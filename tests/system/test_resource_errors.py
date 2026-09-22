"""Never publish generated authentication values on subprocess error paths."""

import subprocess
import sys
import traceback

import pytest

from .harness import Stack


@pytest.mark.parametrize("operation", ["timeout", "launch"])
def test_command_errors_never_disclose_generated_password(operation: str) -> None:
    stack = Stack()
    secret = stack.passwords["postgres"]
    args = ([sys.executable, "-c", "import time; time.sleep(2)",
             f"POSTGRES_PASSWORD={secret}"] if operation == "timeout"
            else [f"/nonexistent/POSTGRES_PASSWORD={secret}"])
    try:
        stack.command(args, timeout=0.02)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        # Boolean assertions intentionally prevent pytest from printing the secret.
        disclosed = secret in "".join(traceback.format_exception(error))
        normalized = isinstance(error, RuntimeError)
        unchained = error.__cause__ is None and error.__suppress_context__
        bounded = len(str(error)) < 200
        contextual = "harness command" in str(error) and operation in str(error)
    else:
        pytest.fail("real subprocess failure was not surfaced")
    assert not disclosed, "generated credential appeared in public traceback"
    assert normalized
    assert unchained
    assert bounded
    assert contextual
