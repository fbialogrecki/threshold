import pytest
from fastapi.testclient import TestClient
from social.api import routes
from social.domain import models
from social.domain.models import Comment, Post, UserBlock
from social.main import app
from social.nats_server import apply_user_block_event
from sqlalchemy import func, select
from sqlalchemy.orm import Session

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
USER_1_HEADERS = {
    **TOKEN_HEADERS,
    "X-Threshold-User-Id": "user-1",
    "X-Threshold-Username": "nightcrawler",
    "X-Threshold-Display-Name": "Night Crawler",
}
USER_2_HEADERS = {
    **TOKEN_HEADERS,
    "X-Threshold-User-Id": "user-2",
    "X-Threshold-Username": "warper",
    "X-Threshold-Display-Name": "Warper",
}


def _erase(client: TestClient, user_id: str) -> None:
    response = client.post(
        "/v1/internal/anonymize-author",
        headers=TOKEN_HEADERS,
        json={"user_id": user_id},
    )
    assert response.status_code == 200


def test_erasure_is_idempotent_and_persists_one_tombstone(session: Session) -> None:
    client = TestClient(app)

    _erase(client, "user-1")
    _erase(client, "user-1")

    tombstone_model = models.AccountErasureTombstone
    assert session.scalar(select(func.count()).select_from(tombstone_model)) == 1
    assert session.get(tombstone_model, "user-1") is not None


def test_erased_actor_cannot_create_any_durable_social_participation(session: Session) -> None:
    client = TestClient(app)
    post = client.post("/v1/posts", headers=USER_2_HEADERS, json={"body": "target"}).json()
    comment = client.post(
        f"/v1/posts/{post['id']}/comments",
        headers=USER_2_HEADERS,
        json={"body": "target comment"},
    ).json()
    _erase(client, "user-1")

    requests = [
        client.post("/v1/groups/techno-warsaw/membership", headers=USER_1_HEADERS),
        client.post("/v1/posts", headers=USER_1_HEADERS, json={"body": "late post"}),
        client.post(
            f"/v1/posts/{post['id']}/comments",
            headers=USER_1_HEADERS,
            json={"body": "late comment"},
        ),
        client.put(
            f"/v1/posts/{post['id']}/reaction",
            headers=USER_1_HEADERS,
            json={"kind": "up"},
        ),
        client.put(
            f"/v1/comments/{comment['id']}/reaction",
            headers=USER_1_HEADERS,
            json={"kind": "up"},
        ),
        client.put(
            f"/v1/posts/{post['id']}/emoji",
            headers=USER_1_HEADERS,
            json={"emoji": "🔥"},
        ),
        client.post(
            "/v1/blocks/user-2",
            headers=USER_1_HEADERS,
            json={"blocked_username": "warper"},
        ),
        client.post(
            "/v1/reports",
            headers=USER_1_HEADERS,
            json={"target_type": "post", "target_id": post["id"], "reason": "spam"},
        ),
    ]

    assert [response.status_code for response in requests] == [410] * len(requests)
    assert (
        session.scalar(
            select(func.count()).select_from(Post).where(Post.author_user_id == "user-1")
        )
        == 0
    )
    assert (
        session.scalar(
            select(func.count()).select_from(Comment).where(Comment.author_user_id == "user-1")
        )
        == 0
    )


def test_erased_target_is_fenced_for_blocks_mentions_and_event_announcements(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(app)
    _erase(client, "user-2")

    async def resolve_erased_user(_settings: object, _handle: str) -> dict[str, str]:
        return {
            "target_type": "user",
            "target_id": "user-2",
            "handle": "warper",
            "display_name": "Warper",
            "target_url": "/profiles/warper",
            "recipient_user_id": "user-2",
        }

    monkeypatch.setattr(routes, "resolve_profile_or_page_mention", resolve_erased_user)

    block = client.post(
        "/v1/blocks/user-2",
        headers=USER_1_HEADERS,
        json={"blocked_username": "warper"},
    )
    mention = client.post(
        "/v1/posts",
        headers=USER_1_HEADERS,
        json={"body": "hello @warper"},
    )
    announcement = client.post(
        "/internal/v1/event-announcements",
        headers=TOKEN_HEADERS,
        json={
            "event_id": "event-after-erasure",
            "event_slug": "event-after-erasure",
            "event_title": "Late Event",
            "city": "Warsaw",
            "page_id": "page-1",
            "actor_user_id": "user-2",
        },
    )

    assert block.status_code == 410
    assert mention.status_code == 410
    assert announcement.status_code == 410


@pytest.mark.parametrize("erased_user_id", ["user-1", "user-2"])
def test_delayed_block_projection_for_erased_actor_or_target_is_dropped(
    session: Session, erased_user_id: str
) -> None:
    _erase(TestClient(app), erased_user_id)

    applied = apply_user_block_event(
        session,
        {
            "action": "blocked",
            "blocker_user_id": "user-1",
            "blocked_user_id": "user-2",
            "blocker_username": "nightcrawler",
            "blocked_username": "warper",
        },
    )
    session.commit()

    assert applied is False
    assert session.scalar(select(UserBlock)) is None
