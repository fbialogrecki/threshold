import json
import logging
from typing import Any

import nats

from social.settings import Settings

logger = logging.getLogger(__name__)


async def list_following_user_ids(settings: Settings, user_id: str) -> set[str]:
    if not settings.nats_enabled:
        return set()

    client = await nats.connect(settings.nats_url)
    try:
        message = await client.request(
            settings.users_list_following_subject,
            json.dumps({"user_id": user_id}).encode("utf-8"),
            timeout=settings.nats_request_timeout_seconds,
        )
        payload: Any = json.loads(message.data.decode("utf-8"))
        if not isinstance(payload, list):
            logger.warning("users list-following returned non-list payload")
            return set()
        ids: set[str] = set()
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("target_id"), str):
                ids.add(item["target_id"])
        return ids
    except Exception:
        logger.exception("users list-following request failed; falling back to group feed only")
        return set()
    finally:
        await client.drain()


async def create_notification(
    settings: Settings,
    *,
    recipient_user_id: str,
    actor_user_id: str | None,
    event_type: str,
    target_type: str,
    target_id: str,
    title: str,
    target_url: str | None = None,
    body: str | None = None,
    dedupe_key: str | None = None,
    metadata: dict[str, str | int | bool | None] | None = None,
) -> None:
    if actor_user_id == recipient_user_id:
        return
    if not settings.users_service_url or not settings.threshold_internal_token:
        logger.warning("users notification client is not configured; skipping notification")
        return
    import httpx

    try:
        async with httpx.AsyncClient(timeout=settings.nats_request_timeout_seconds) as client:
            response = await client.post(
                f"{settings.users_service_url.rstrip('/')}/internal/v1/notifications",
                headers={"X-Threshold-Internal-Token": settings.threshold_internal_token},
                json={
                    "recipient_user_id": recipient_user_id,
                    "actor_user_id": actor_user_id,
                    "type": event_type,
                    "target_type": target_type,
                    "target_id": target_id,
                    "target_url": target_url,
                    "title": title,
                    "body": body,
                    "dedupe_key": dedupe_key,
                    "metadata": metadata or {},
                },
            )
            response.raise_for_status()
    except Exception:
        logger.exception("users notification create failed")


async def resolve_profile_or_page_mention(
    settings: Settings, handle: str
) -> dict[str, str | None] | None:
    if not settings.users_service_url or not settings.threshold_internal_token:
        logger.warning("users mention resolver is not configured")
        return None
    import httpx

    async with httpx.AsyncClient(timeout=settings.nats_request_timeout_seconds) as client:
        for kind in ("profiles", "pages"):
            response = await client.get(
                f"{settings.users_service_url.rstrip('/')}/internal/v1/mention-targets/{kind}/{handle}",
                headers={"X-Threshold-Internal-Token": settings.threshold_internal_token},
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            payload: Any = response.json()
            if isinstance(payload, dict):
                return {str(key): value for key, value in payload.items()}
    return None


async def resolve_event_mention(settings: Settings, slug: str) -> dict[str, str | None] | None:
    if not settings.events_service_url or not settings.threshold_internal_token:
        logger.warning("events mention resolver is not configured")
        return None
    import httpx

    async with httpx.AsyncClient(timeout=settings.nats_request_timeout_seconds) as client:
        response = await client.get(
            f"{settings.events_service_url.rstrip('/')}/internal/v1/mention-targets/events/{slug}",
            headers={"X-Threshold-Internal-Token": settings.threshold_internal_token},
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload: Any = response.json()
        if isinstance(payload, dict):
            return {str(key): value for key, value in payload.items()}
    return None
