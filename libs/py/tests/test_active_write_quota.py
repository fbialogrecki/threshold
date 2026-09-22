from collections import defaultdict, deque
from importlib.util import find_spec

import pytest
from fastapi import HTTPException

from threshold_common.api_security import check_write_quota


def test_always_allow_rate_limit_placeholder_is_not_importable() -> None:
    assert find_spec("threshold_common.rate_limit") is None


def test_exhausted_write_quota_rejects_without_recording_denied_attempt() -> None:
    attempts: dict[str, deque[float]] = defaultdict(deque)
    check_write_quota(attempts, user_id="writer", count=1, window_seconds=60)
    accepted = list(attempts["writer"])

    for _ in range(2):
        with pytest.raises(HTTPException) as exc:
            check_write_quota(attempts, user_id="writer", count=1, window_seconds=60)
        assert exc.value.status_code == 429
        assert exc.value.detail == "rate limit exceeded"
        assert list(attempts["writer"]) == accepted

    check_write_quota(attempts, user_id="other-writer", count=1, window_seconds=60)
    assert len(attempts["other-writer"]) == 1


def test_zero_write_quota_rejects_first_attempt() -> None:
    attempts: dict[str, deque[float]] = defaultdict(deque)
    with pytest.raises(HTTPException) as exc:
        check_write_quota(attempts, user_id="writer", count=0, window_seconds=60)
    assert exc.value.status_code == 429
    assert not attempts["writer"]
