import asyncio
import json
import logging
from typing import Any

import nats

from users.settings import Settings

logger = logging.getLogger(__name__)


async def _publish(settings: Settings, subject: str, payload: dict[str, Any]) -> None:
    client = await nats.connect(settings.nats_url)
    try:
        await client.publish(subject, json.dumps(payload).encode("utf-8"))
        await client.flush(timeout=max(1, int(settings.social_request_timeout_seconds)))
    finally:
        await client.drain()


def publish_user_block_changed(settings: Settings, payload: dict[str, Any]) -> None:
    if not settings.nats_enabled:
        return
    try:
        asyncio.run(_publish(settings, settings.user_block_changed_subject, payload))
    except Exception:
        logger.exception("users block projection event publish failed")
