"""Real HTTP/cookie boundary and a nonempty NATS-off group-feed control."""

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from uuid import uuid4

import httpx
import pytest

from .harness import Stack

type User = dict[str, object]
type FeedCase = tuple[
    Stack, httpx.Client, User, User, httpx.Client, Callable[[User], dict[str, str]], str,
]


def register(client: httpx.Client, name: str) -> User:
    response = client.post("/v1/auth/register", json={
        "email": f"{name}@example.test", "username": name,
        "password": f"Synthetic1!{uuid4().hex}", "display_name": name,
    })
    assert response.status_code == 201
    assert response.cookies.get("threshold_session")
    assert response.cookies.get("threshold_refresh")
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/v1/auth/me").json()["user"]["id"] == response.json()["user"]["id"]
    user: object = response.json()["user"]
    assert isinstance(user, dict)
    assert all(isinstance(key, str) for key in user)
    return user


@pytest.fixture()
def feed_case(http_stack: Stack) -> Iterator[FeedCase]:
    stack = http_stack
    with ExitStack() as clients:
        viewer = clients.enter_context(httpx.Client(base_url=stack.urls["users"],
                                                    trust_env=False, timeout=3))
        author = clients.enter_context(httpx.Client(base_url=stack.urls["users"],
                                                    trust_env=False, timeout=3))
        viewer_user = register(viewer, f"viewer_{uuid4().hex[:12]}")
        author_user = register(author, f"author_{uuid4().hex[:12]}")
        social = clients.enter_context(httpx.Client(base_url=stack.urls["social"],
                                                    trust_env=False, timeout=3))
        def headers(user: User) -> dict[str, str]:
            identifier, username = user["id"], user["username"]
            assert isinstance(identifier, str) and isinstance(username, str)
            return {"X-Threshold-Internal-Token": stack.token,
                    "X-Threshold-User-Id": identifier,
                    "X-Threshold-Username": username,
                    "X-Threshold-Display-Name": username}

        slug = f"synthetic-{uuid4().hex}"
        group_id = str(uuid4())
        # Official groups are deployment seed data, not a fake admin endpoint.
        with stack.connect("social", "social_runtime") as conn:
            conn.execute("INSERT INTO groups (id, slug, name, city, official, created_at) "
                         "VALUES (%s, %s, 'Synthetic group', 'Synthetic', true, now())",
                         (group_id, slug))
        for user in (viewer_user, author_user):
            assert social.post(f"/v1/groups/{slug}/membership",
                               headers=headers(user)).status_code == 200
        post = social.post("/v1/posts", headers=headers(author_user),
                           json={"body": "Synthetic positive feed control", "group_slug": slug})
        assert post.status_code == 201
        post_id: object = post.json()["id"]
        assert isinstance(post_id, str)
        response = social.get("/v1/feed", headers=headers(viewer_user))
        assert response.status_code == 200
        assert post_id in {item["id"] for item in response.json()["items"]}, \
            "nonempty pre-block group feed is mandatory with NATS disabled"
        yield stack, viewer, viewer_user, author_user, social, headers, post_id


def test_real_cookie_internal_token_and_nonempty_feed_control(feed_case: FeedCase) -> None:
    stack, viewer, viewer_user, author_user, social, headers, post_id = feed_case
    assert len({process.pid for process in stack.processes}) == 2
    assert all(process.poll() is None for process in stack.processes)
    viewer_id = viewer_user["id"]
    assert isinstance(viewer_id, str)
    check = f"/internal/v1/users/{viewer_user['id']}/blocks/{author_user['id']}"
    for supplied in ({}, {"X-Threshold-Internal-Token": "invalid"}):
        assert viewer.get(check, headers=supplied).status_code == 401
        assert social.get("/v1/feed", headers={**supplied,
                          "X-Threshold-User-Id": viewer_id}).status_code == 401
    assert viewer.get(check, headers=headers(viewer_user)).json() == {"blocked": False}
    with httpx.Client(base_url=stack.urls["users"], trust_env=False, timeout=3) as stranger:
        assert stranger.post("/v1/me/blocks", headers=headers(viewer_user),
                             json={"username": author_user["username"]}).status_code == 401
    assert post_id


def test_acknowledged_block_hides_post_when_nats_event_is_missed(feed_case: FeedCase) -> None:
    stack, viewer, viewer_user, author_user, social, headers, post_id = feed_case
    # Both real services run NATS-disabled; no projection is injected or mocked.
    acknowledgement = viewer.post("/v1/me/blocks",
                                  json={"username": author_user["username"]})
    assert acknowledgement.status_code == 201
    assert acknowledgement.json() == {"status": "ok"}
    check = f"/internal/v1/users/{viewer_user['id']}/blocks/{author_user['id']}"
    canonical = viewer.get(check, headers=headers(viewer_user))
    assert canonical.status_code == 200
    assert canonical.json() == {"blocked": True}
    response = social.get("/v1/feed", headers=headers(viewer_user))
    assert response.status_code == 200
    assert post_id not in {item["id"] for item in response.json()["items"]}, \
        "W05: users acknowledged the canonical block but social still exposes the blocked author"
