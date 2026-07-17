import json
import logging
from typing import Any

import auth_gateway.users_client as users_client
import httpx
import pytest
from auth_gateway.users_client import UsersProfileClient, UsersProfileClientError


def client(*, transport: str = "http", internal_token: str | None = "test-internal-token"):
    return UsersProfileClient(
        base_url="http://users.test",
        timeout_seconds=1,
        transport="nats" if transport == "nats" else "http",
        internal_token=internal_token,
        nats_url="nats://nats.test:4222",
    )


@pytest.mark.asyncio
async def test_http_profile_request_sends_internal_token(monkeypatch) -> None:
    request: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"user": {"id": "user-1"}}

    class FakeAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 1

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> FakeResponse:
            request.update(url=url, **kwargs)
            return FakeResponse()

    monkeypatch.setattr(users_client.httpx, "AsyncClient", FakeAsyncClient)

    await client().current_profile(subject="subject", email=None, username="ada")

    assert request["url"] == "http://users.test/internal/v1/current-profile"
    assert request["headers"] == {"X-Threshold-Internal-Token": "test-internal-token"}


@pytest.mark.asyncio
async def test_http_profile_request_fails_closed_without_internal_token(monkeypatch) -> None:
    class UnexpectedAsyncClient:
        def __init__(self, **_: object) -> None:
            raise AssertionError("HTTP request must not start without an internal token")

    monkeypatch.setattr(users_client.httpx, "AsyncClient", UnexpectedAsyncClient)

    with pytest.raises(
        UsersProfileClientError, match="users profile HTTP transport is not configured"
    ):
        await client(internal_token=None).current_profile(
            subject="subject", email=None, username=None
        )


@pytest.mark.asyncio
async def test_http_profile_errors_and_logs_do_not_expose_internal_token(
    monkeypatch, caplog
) -> None:
    token = "do-not-log-this-token"

    class FailingAsyncClient:
        def __init__(self, **_: object) -> None:
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *_: object, **__: object) -> None:
            raise httpx.ConnectError(f"connection failed: {token}")

    monkeypatch.setattr(users_client.httpx, "AsyncClient", FailingAsyncClient)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(UsersProfileClientError) as exc_info:
        await client(internal_token=token).current_profile(
            subject="subject", email=None, username=None
        )

    assert str(exc_info.value) == "users profile HTTP request failed"
    assert token not in str(exc_info.value)
    assert token not in caplog.text


@pytest.mark.asyncio
async def test_nats_profile_request_does_not_send_internal_token(monkeypatch) -> None:
    request: dict[str, Any] = {}

    class FakeResponse:
        data = b'{"user":{"id":"user-1"}}'

    class FakeNatsClient:
        async def request(self, subject: str, payload: bytes, **kwargs: object) -> FakeResponse:
            request.update(subject=subject, payload=payload, **kwargs)
            return FakeResponse()

        async def close(self) -> None:
            return None

    async def fake_connect(url: str) -> FakeNatsClient:
        assert url == "nats://nats.test:4222"
        return FakeNatsClient()

    monkeypatch.setattr(users_client.nats, "connect", fake_connect)

    response = await client(transport="nats").current_profile(
        subject="subject", email="ada@example.test", username="ada"
    )

    assert response == {"user": {"id": "user-1"}}
    assert request["subject"] == "users.current_profile.v1"
    assert json.loads(request["payload"]) == {
        "authentik_subject": "subject",
        "email": "ada@example.test",
        "username": "ada",
    }
    assert "X-Threshold-Internal-Token" not in request["headers"]
    assert "test-internal-token" not in repr(request)
