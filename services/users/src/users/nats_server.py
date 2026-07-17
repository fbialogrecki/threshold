import json
import logging
from typing import Any

import nats
from nats.aio.client import Client as NatsClient
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from threshold_common.otel_nats import get_message_headers, nats_consumer_span
from users.api.routes import _profile_response
from users.api.schemas import CurrentPrincipalRequest, ListFollowingRequest
from users.domain.follows import canonical_follow_target_type
from users.domain.profiles import get_or_create_current_profile
from users.settings import Settings

logger = logging.getLogger(__name__)

_settings = Settings()
type ListFollowingResponse = list[dict[str, str]] | dict[str, str]


class UsersNatsServer:
    def __init__(
        self,
        *,
        nats_url: str,
        subject: str,
        list_following_subject: str = _settings.users_list_following_subject,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.nats_url = nats_url
        self.subject = subject
        self.list_following_subject = list_following_subject
        self.session_factory = session_factory
        self._client: NatsClient | None = None

    async def start(self) -> None:
        client = await nats.connect(self.nats_url)
        await client.subscribe(self.subject, cb=self._handle_current_profile)
        await client.subscribe(self.list_following_subject, cb=self._handle_list_following)
        await client.flush()
        self._client = client
        logger.info(
            "users NATS responder started",
            extra={"subject": self.subject, "list_following_subject": self.list_following_subject},
        )

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.drain()
            self._client = None

    async def _handle_current_profile(self, message: Any) -> None:
        with nats_consumer_span(
            subject=self.subject,
            headers=get_message_headers(message),
            span_name="users.current_profile NATS handler",
        ):
            try:
                payload = CurrentPrincipalRequest.model_validate_json(message.data)
                with self.session_factory() as session:
                    user = get_or_create_current_profile(
                        session,
                        authentik_subject=payload.authentik_subject,
                        email=payload.email,
                        username=payload.username,
                    )
                    response = _profile_response(user).model_dump(mode="json")
                    logger.info("users current-profile NATS request handled")
            except ValidationError as exc:
                logger.warning("invalid users current-profile NATS request", exc_info=exc)
                response = {"error": "invalid_request"}
            except Exception:
                logger.exception("users current-profile NATS handler failed")
                response = {"error": "internal_error"}

        if message.reply:
            await message.respond(json.dumps(response).encode("utf-8"))

    async def _handle_list_following(self, message: Any) -> None:
        with nats_consumer_span(
            subject=self.list_following_subject,
            headers=get_message_headers(message),
            span_name="users.list_following NATS handler",
        ):
            try:
                payload = ListFollowingRequest.model_validate_json(message.data)
                response: ListFollowingResponse
                with self.session_factory() as session:
                    from sqlalchemy import select

                    from users.domain.models import ApplicationUser, Follow, Page

                    follows = session.scalars(
                        select(Follow).where(Follow.follower_user_id == payload.user_id)
                    ).all()

                    response = []
                    seen: set[tuple[str, str]] = set()
                    for f in follows:
                        target_type = canonical_follow_target_type(f.target_type)
                        key = (target_type, f.target_id)
                        if key in seen:
                            continue
                        seen.add(key)
                        display_name = f.target_handle
                        if target_type in {"consumer", "artist"}:
                            target_user = session.get(ApplicationUser, f.target_id)
                            if target_user is not None and target_user.status != "deleted":
                                if (
                                    target_user.consumer_profile is not None
                                    and target_user.consumer_profile.display_name
                                ):
                                    display_name = target_user.consumer_profile.display_name
                                elif target_user.username:
                                    display_name = target_user.username
                        elif target_type == "page":
                            page = session.get(Page, f.target_id)
                            if page is not None:
                                display_name = page.display_name

                        response.append(
                            {
                                "target_type": target_type,
                                "target_id": f.target_id,
                                "target_handle": f.target_handle,
                                "display_name": display_name,
                            }
                        )

                    logger.info("users list-following NATS request handled")
            except ValidationError as exc:
                logger.warning("invalid users list-following NATS request", exc_info=exc)
                response = {"error": "invalid_request"}
            except Exception:
                logger.exception("users list-following NATS handler failed")
                response = {"error": "internal_error"}

        if message.reply:
            await message.respond(json.dumps(response).encode("utf-8"))
