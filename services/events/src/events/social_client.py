import logging

import httpx

from events.domain.models import Event
from events.settings import Settings

logger = logging.getLogger(__name__)


def announce_event(settings: Settings, event: Event) -> bool:
    if not settings.social_service_url or not settings.threshold_internal_token:
        logger.warning("social event announcement is not configured", extra={"event_id": event.id})
        return False
    try:
        response = httpx.post(
            f"{settings.social_service_url.rstrip('/')}/internal/v1/event-announcements",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token},
            json={
                "event_id": event.id,
                "event_slug": event.slug,
                "event_title": event.title,
                "city": event.city,
                "page_id": event.page_id,
                "actor_user_id": event.created_by_user_id,
            },
            timeout=3.0,
        )
        if response.status_code == 404:
            logger.warning(
                "official city group not found for event announcement",
                extra={"event_id": event.id, "city": event.city},
            )
            return False
        response.raise_for_status()
        return True
    except Exception:
        logger.exception("event announcement failed", extra={"event_id": event.id})
        return False
