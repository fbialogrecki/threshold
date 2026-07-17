import json
from typing import Any, Literal

import httpx
import nats
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from threshold_common.otel_nats import inject_trace_context


class UsersProfileClientError(RuntimeError):
    """Raised when auth-gateway cannot fetch the application profile."""


class UsersProfileClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        transport: Literal["http", "nats"] = "http",
        internal_token: str | None = None,
        nats_url: str | None = None,
        nats_subject: str = "users.current_profile.v1",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.internal_token = internal_token
        self.nats_url = nats_url
        self.nats_subject = nats_subject

    async def current_profile(
        self,
        *,
        subject: str,
        email: str | None,
        username: str | None,
    ) -> dict[str, Any]:
        payload = {
            "authentik_subject": subject,
            "email": email,
            "username": username,
        }
        if self.transport == "nats":
            return await self._current_profile_nats(payload)
        return await self._current_profile_http(payload)

    async def _current_profile_http(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.internal_token:
            raise UsersProfileClientError("users profile HTTP transport is not configured")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/internal/v1/current-profile",
                    headers={"X-Threshold-Internal-Token": self.internal_token},
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError:
            raise UsersProfileClientError("users profile HTTP request failed") from None

        data = response.json()
        if not isinstance(data, dict):
            raise UsersProfileClientError("users profile response is invalid")
        return data

    async def _current_profile_nats(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.nats_url:
            raise UsersProfileClientError("NATS URL is not configured")

        nc = await nats.connect(self.nats_url)
        try:
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(
                "auth-gateway.nats.users.current_profile",
                kind=SpanKind.CLIENT,
                attributes={
                    "messaging.system": "nats",
                    "messaging.destination.name": self.nats_subject,
                },
            ):
                response = await nc.request(
                    self.nats_subject,
                    json.dumps(payload).encode("utf-8"),
                    headers=inject_trace_context(),
                    timeout=self.timeout_seconds,
                )
        except TimeoutError as exc:
            raise UsersProfileClientError("users profile NATS request timed out") from exc
        except Exception as exc:
            raise UsersProfileClientError("users profile NATS request failed") from exc
        finally:
            await nc.close()

        try:
            data = json.loads(response.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UsersProfileClientError("users profile NATS response is invalid JSON") from exc

        if not isinstance(data, dict):
            raise UsersProfileClientError("users profile response is invalid")
        if data.get("error"):
            raise UsersProfileClientError("users profile NATS responder returned an error")
        return data
