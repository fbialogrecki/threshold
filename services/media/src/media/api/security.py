from fastapi import Header, HTTPException, status
from media.main_dependencies import settings

from perlimen_common.api_security import check_internal_token


def require_internal_token(
    x_perlimen_internal_token: str | None = Header(
        default=None, alias="X-Threshold-Internal-Token"
    ),
) -> None:
    check_internal_token(
        settings.perlimen_internal_token,
        x_perlimen_internal_token,
        invalid_detail="invalid internal token",
    )


def require_user_id(
    x_perlimen_user_id: str | None = Header(default=None, alias="X-Threshold-User-Id"),
) -> str:
    if not x_perlimen_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing user id")
    return x_perlimen_user_id
