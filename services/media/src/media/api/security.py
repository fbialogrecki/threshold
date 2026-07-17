from fastapi import Header, HTTPException, status
from media.main_dependencies import settings

from threshold_common.api_security import check_internal_token


def require_internal_token(
    x_threshold_internal_token: str | None = Header(default=None),
) -> None:
    check_internal_token(
        settings.threshold_internal_token,
        x_threshold_internal_token,
        invalid_detail="invalid internal token",
    )


def require_user_id(x_threshold_user_id: str | None = Header(default=None)) -> str:
    if not x_threshold_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing user id")
    return x_threshold_user_id
