import json
import logging
from typing import Any

import nats

from social.settings import Settings

logger = logging.getLogger(__name__)


async def publish_event(settings: Settings, subject: str, payload: dict[str, Any]) -> None:
    if not settings.nats_enabled:
        return

    try:
        client = await nats.connect(settings.nats_url)
        try:
            await client.publish(subject, json.dumps(payload).encode("utf-8"))
            await client.flush(timeout=max(1, int(settings.nats_request_timeout_seconds)))
        finally:
            await client.drain()
    except Exception:
        logger.exception("social event publish failed", extra={"subject": subject})
