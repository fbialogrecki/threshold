import logging

import httpx

from users.settings import Settings

logger = logging.getLogger(__name__)


def anonymize_social_author(settings: Settings, user_id: str) -> None:
    if not settings.social_service_url or not settings.threshold_internal_token:
        raise RuntimeError("social anonymize config is missing")

    try:
        response = httpx.post(
            f"{settings.social_service_url.rstrip('/')}/v1/internal/anonymize-author",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token},
            json={"user_id": user_id},
            timeout=settings.social_request_timeout_seconds,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("social anonymize request failed")
        raise
