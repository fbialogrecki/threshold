from collections import defaultdict, deque
from typing import Annotated

from events.main_dependencies import settings
from fastapi import Depends, Header

from threshold_common.api_security import (
    CurrentUser as CurrentUser,
)
from threshold_common.api_security import (
    check_internal_token,
    check_write_quota,
    current_user_from_headers,
)

_write_attempts: dict[str, deque[float]] = defaultdict(deque)


def require_internal_token(
    token: Annotated[str | None, Header(alias="X-Threshold-Internal-Token")] = None,
) -> None:
    check_internal_token(settings.threshold_internal_token, token)


def require_current_user(
    _: Annotated[None, Depends(require_internal_token)],
    user_id: Annotated[str | None, Header(alias="X-Threshold-User-Id")] = None,
    username: Annotated[str | None, Header(alias="X-Threshold-Username")] = None,
    display_name: Annotated[str | None, Header(alias="X-Threshold-Display-Name")] = None,
) -> CurrentUser:
    return current_user_from_headers(
        user_id=user_id, username=username, display_name=display_name
    )


def require_write_quota(user: Annotated[CurrentUser, Depends(require_current_user)]) -> None:
    check_write_quota(
        _write_attempts,
        user_id=user.user_id,
        count=settings.write_rate_limit_count,
        window_seconds=settings.write_rate_limit_window_seconds,
    )


def reset_write_quota_for_tests() -> None:
    _write_attempts.clear()
