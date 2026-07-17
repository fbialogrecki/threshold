import json
import logging
from typing import Any

import nats
from nats.aio.client import Client as NatsClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from social.domain.models import UserBlock
from social.settings import Settings
from threshold_common.otel_nats import get_message_headers, nats_consumer_span

logger = logging.getLogger(__name__)


def _string_payload(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def apply_user_block_event(session: Session, payload: dict[str, Any]) -> None:
    action = _string_payload(payload, "action")
    blocker_user_id = _string_payload(payload, "blocker_user_id")
    blocked_user_id = _string_payload(payload, "blocked_user_id")
    blocker_username = payload.get("blocker_username")
    blocked_username = payload.get("blocked_username")

    block = session.scalar(
        select(UserBlock).where(
            UserBlock.blocker_user_id == blocker_user_id,
            UserBlock.blocked_user_id == blocked_user_id,
        )
    )
    if action == "blocked":
        if block is None:
            block = UserBlock(
                blocker_user_id=blocker_user_id,
                blocked_user_id=blocked_user_id,
            )
        block.blocker_username = blocker_username if isinstance(blocker_username, str) else None
        block.blocked_username = blocked_username if isinstance(blocked_username, str) else None
        session.add(block)
        return
    if action == "unblocked":
        if block is not None:
            session.delete(block)
        return
    raise ValueError("unsupported block action")


class SocialNatsServer:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self._client: NatsClient | None = None

    async def start(self) -> None:
        client = await nats.connect(self.settings.nats_url)
        await client.subscribe(
            self.settings.user_block_changed_subject,
            cb=self._handle_user_block_changed,
        )
        await client.flush()
        self._client = client
        logger.info(
            "social NATS consumers started",
            extra={"user_block_changed_subject": self.settings.user_block_changed_subject},
        )

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.drain()
            self._client = None

    async def _handle_user_block_changed(self, message: Any) -> None:
        with nats_consumer_span(
            subject=self.settings.user_block_changed_subject,
            headers=get_message_headers(message),
            span_name="social.user_block_changed NATS handler",
        ):
            try:
                payload = json.loads(message.data.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
                with self.session_factory() as session:
                    apply_user_block_event(session, payload)
                    session.commit()
            except Exception:
                logger.exception("social user-block projection failed")
