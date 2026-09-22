"""Finite SQLite candidates plus canonical HTTP transport boundary controls."""

import asyncio
import json
import time
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from social.api import routes
from social.domain.models import Group, GroupMembership, Post
from social.main import app
from sqlalchemy import event, select

HEADERS = {
    "X-Threshold-Internal-Token": "test-internal-token",
    "X-Threshold-User-Id": "viewer",
    "X-Threshold-Username": "viewer",
}


def seed(session, count, allowed):
    group = session.scalar(select(Group))
    session.add(GroupMembership(group_id=group.id, user_id="viewer"))
    for i in range(count):
        session.add(
            Post(
                id=f"{count - i:036d}",
                group_id=group.id,
                author_user_id="allow" if i in allowed else "deny",
                author_username="author",
                author_display_name="Author",
                body="control",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    session.commit()


def transport(monkeypatch, delay=0):
    calls = []
    factory = httpx.AsyncClient

    async def handler(request):
        calls.append(json.loads(request.content))
        await asyncio.sleep(delay)
        return httpx.Response(
            200,
            json={
                "viewer_id": "viewer",
                "decisions": [
                    {"target_id": target, "allowed": target == "allow"}
                    for target in calls[-1]["target_ids"]
                ],
            },
        )

    monkeypatch.setattr(routes.settings, "users_service_url", "http://canonical.test")
    monkeypatch.setattr(routes.settings, "nats_request_timeout_seconds", 10)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: factory(**kw, transport=httpx.MockTransport(handler))
    )
    return calls


def test_healthy_denied_batches_equal_timestamp_pagination(session, monkeypatch):
    seed(session, 205, {199, 201, 204})
    calls = transport(monkeypatch)
    client = TestClient(app)
    first = client.get("/v1/feed?limit=2", headers=HEADERS)
    assert first.status_code == 200
    assert [p["id"] for p in first.json()["items"]] == [f"{6:036d}", f"{4:036d}"]
    assert len(calls) == 3
    second = client.get(
        "/v1/feed", params={"limit": 2, "before": first.json()["next_before"]}, headers=HEADERS
    )
    assert [p["id"] for p in second.json()["items"]] == [f"{1:036d}"]
    assert second.json()["next_before"] is None


@pytest.mark.parametrize(
    "count,allowed,status", [(499, {497, 498}, 200), (501, {500}, 503), (500, set(), 503)]
)
def test_candidate_budget_and_constant_cursor_sql(session, monkeypatch, count, allowed, status):
    seed(session, count, allowed)
    calls = transport(monkeypatch)
    queries = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if "FROM posts" in statement and "ORDER BY posts.created_at DESC" in statement:
            queries.append(statement)

    event.listen(session.bind, "before_cursor_execute", record)
    response = TestClient(app).get("/v1/feed?limit=2", headers=HEADERS)
    assert response.status_code == status
    assert len(calls) == 5
    assert len(queries) == 5
    assert len(set(queries[1:])) == 1
    if status == 200:
        assert len(response.json()["items"]) == 2
        assert response.json()["next_before"] is None
    else:
        assert "items" not in response.json()


def test_total_delayed_transport_deadline(session, monkeypatch):
    seed(session, 401, {400})
    calls = transport(monkeypatch, delay=0.8)
    start = time.monotonic()
    response = TestClient(app).get("/v1/feed?limit=1", headers=HEADERS)
    assert response.status_code == 503
    assert 2.8 <= time.monotonic() - start < 3.8
    assert len(calls) <= 4


def test_synchronous_serialization_overrun_is_not_success(session, monkeypatch):
    seed(session, 1, {0})
    transport(monkeypatch)
    original = routes._posts_response

    def delayed(*args):
        time.sleep(3.05)
        return original(*args)

    monkeypatch.setattr(routes, "_posts_response", delayed)
    assert TestClient(app).get("/v1/feed", headers=HEADERS).status_code == 503
