from dataclasses import dataclass

import httpx

from users.settings import Settings


class MediaAssetValidationError(Exception):
    pass


@dataclass(frozen=True)
class MediaAssetRef:
    id: str
    owner_user_id: str
    context: str
    status: str


def get_media_asset(settings: Settings, asset_id: str) -> MediaAssetRef:
    if not settings.media_service_url or not settings.threshold_internal_token:
        raise MediaAssetValidationError("media validation is not configured")
    try:
        response = httpx.get(
            f"{settings.media_service_url.rstrip('/')}/internal/v1/assets/{asset_id}",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token},
            timeout=settings.media_request_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise MediaAssetValidationError("media validation failed") from exc
    if response.status_code == 404:
        raise MediaAssetValidationError("media asset not found")
    if response.status_code >= 400:
        raise MediaAssetValidationError("media validation failed")
    body = response.json()
    return MediaAssetRef(
        id=body["id"],
        owner_user_id=body["owner_user_id"],
        context=body["context"],
        status=body["status"],
    )


def validate_avatar_asset(
    settings: Settings,
    *,
    asset_id: str,
    owner_user_id: str,
    allowed_contexts: set[str],
) -> None:
    asset = get_media_asset(settings, asset_id)
    if asset.owner_user_id != owner_user_id:
        raise MediaAssetValidationError("media asset owner mismatch")
    if asset.context not in allowed_contexts:
        raise MediaAssetValidationError("media asset context mismatch")
    if asset.status != "ready":
        raise MediaAssetValidationError("media asset is not ready")
