from events.settings import Settings
from threshold_common.media_client import (
    MediaAssetRef,
    MediaAssetValidationError,
    get_media_asset,
    validate_media_asset,
)

__all__ = [
    "MediaAssetRef",
    "MediaAssetValidationError",
    "get_media_asset",
    "validate_event_poster_asset",
]


def validate_event_poster_asset(settings: Settings, *, asset_id: str, owner_user_id: str) -> None:
    validate_media_asset(
        settings, asset_id=asset_id, owner_user_id=owner_user_id, context="event_poster"
    )
