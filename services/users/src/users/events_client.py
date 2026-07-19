import logging

import httpx

from users.settings import Settings

logger = logging.getLogger(__name__)


def erase_events_account(
    settings: Settings, user_id: str, artist_profile_ids: list[str]
) -> None:
    if not settings.events_service_url or not settings.threshold_internal_token:
        raise RuntimeError("events erasure config is missing")

    try:
        response = httpx.post(
            f"{settings.events_service_url.rstrip('/')}/internal/v1/account-erasure",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token},
            json={"user_id": user_id, "artist_profile_ids": artist_profile_ids},
            timeout=settings.events_request_timeout_seconds,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("events account erasure request failed")
        raise
