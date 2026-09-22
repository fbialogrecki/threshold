import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from social.settings import Settings

from social import users_client


def run_client(monkeypatch, handler, targets=None):
    factory = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: factory(**kw, transport=httpx.MockTransport(handler))
    )
    assert hasattr(users_client, "block_decisions"), "canonical client missing"
    settings = Settings()
    settings.users_service_url = "http://users"
    settings.threshold_internal_token = "secret"
    return asyncio.run(
        users_client.block_decisions(
            settings,
            "viewer",
            ["author"] if targets is None else targets,
        )
    )


def test_canonical_client_deduplicates_literal_ids_and_chunks(monkeypatch):
    batches = []

    def handler(request):
        body = json.loads(request.content)
        assert request.url.path == "/internal/v1/users/block-decisions"
        assert request.headers["X-Threshold-Internal-Token"] == "secret"
        assert body["viewer_id"] == "viewer"
        batches.append(body["target_ids"])
        return httpx.Response(
            200,
            json={
                "viewer_id": "viewer",
                "decisions": [
                    {"target_id": target, "allowed": target != " Author "}
                    for target in body["target_ids"]
                ],
            },
        )

    targets = [" Author "] + [str(i) for i in range(100)] + [" Author "]
    decisions = run_client(monkeypatch, handler, targets)
    assert [len(batch) for batch in batches] == [100, 1]
    assert decisions[" Author "] is False
    assert len(decisions) == 101


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"viewer_id": "other", "decisions": []},
        {"viewer_id": "viewer", "decisions": []},
        {"viewer_id": "viewer", "decisions": [{"target_id": "author", "allowed": 1}]},
        {"viewer_id": "viewer", "decisions": [{"target_id": "other", "allowed": True}]},
        {"viewer_id": "viewer", "decisions": [{"target_id": "author", "allowed": True}] * 2},
        {
            "viewer_id": "viewer",
            "decisions": [{"target_id": "author", "allowed": True, "extra": True}],
        },
        {
            "viewer_id": "viewer",
            "decisions": [{"target_id": "author", "allowed": True}],
            "extra": True,
        },
    ],
)
def test_malformed_decisions_fail_closed(monkeypatch, payload):
    with pytest.raises(HTTPException) as error:
        run_client(monkeypatch, lambda request: httpx.Response(200, json=payload))
    assert error.value.status_code == 503


@pytest.mark.parametrize(
    "payload",
    [
        b'{"viewer_id":"other","viewer_id":"viewer",'
        b'"decisions":[{"target_id":"author","allowed":true}]}',
        b'{"viewer_id":"viewer","decisions":[], '
        b'"decisions":[{"target_id":"author","allowed":true}]}',
        b'{"viewer_id":"viewer","decisions":[{'
        b'"target_id":"other","target_id":"author","allowed":true}]}',
        b'{"viewer_id":"viewer","decisions":[{'
        b'"target_id":"author","allowed":false,"allowed":true}]}',
        b'{"viewer_id":"viewer","decisions":[{'
        b'"target_id":"author","allowed":true,"allowed":true}]}',
    ],
    ids=["viewer", "decisions", "target_id", "deny_then_allow", "identical_allowed"],
)
def test_duplicate_json_members_fail_closed(monkeypatch, payload):
    with pytest.raises(HTTPException) as error:
        run_client(monkeypatch, lambda request: httpx.Response(200, content=payload))
    assert error.value.status_code == 503
    assert error.value.detail == "block policy unavailable"


@pytest.mark.parametrize("allowed", [True, False], ids=["allow", "deny"])
def test_raw_json_healthy_decisions(monkeypatch, allowed):
    payload = (
        b'{"viewer_id":"viewer","decisions":[{"target_id":"author","allowed":'
        + (b"true" if allowed else b"false")
        + b"}]}"
    )
    assert run_client(monkeypatch, lambda request: httpx.Response(200, content=payload)) == {
        "author": allowed
    }


@pytest.mark.parametrize("failure", ["timeout", "status", "json", "oversize", "redirect"])
def test_unavailable_decisions_fail_closed(monkeypatch, failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("unavailable")
        if failure == "oversize":
            return httpx.Response(200, content=b" " * 32769)
        if failure == "redirect":
            return httpx.Response(307, headers={"Location": "http://other"})
        return httpx.Response(503 if failure == "status" else 200, content=b"invalid")

    with pytest.raises(HTTPException) as error:
        run_client(monkeypatch, handler)
    assert error.value.status_code == 503
