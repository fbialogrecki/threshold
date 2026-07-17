import hmac
import time
from collections import deque
from dataclasses import dataclass

from fastapi import HTTPException, status


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    username: str
    display_name: str


def check_internal_token(
    expected: str | None, token: str | None, *, invalid_detail: str = "unauthorized"
) -> None:
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="internal token is not configured",
        )
    if token is None or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=invalid_detail)


def current_user_from_headers(
    *, user_id: str | None, username: str | None, display_name: str | None
) -> CurrentUser:
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user id required")
    safe_username = (username or "deleted-user").strip() or "deleted-user"
    safe_display_name = (display_name or safe_username).strip() or safe_username
    return CurrentUser(user_id=user_id, username=safe_username, display_name=safe_display_name)


def check_write_quota(
    attempts: dict[str, deque[float]], *, user_id: str, count: int, window_seconds: int
) -> None:
    now = time.monotonic()
    window_start = now - window_seconds
    user_attempts = attempts[user_id]
    while user_attempts and user_attempts[0] <= window_start:
        user_attempts.popleft()
    if len(user_attempts) >= count:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded",
        )
    user_attempts.append(now)
