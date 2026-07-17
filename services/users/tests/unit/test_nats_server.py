import json
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from users.db.base import Base
from users.nats_server import UsersNatsServer


class FakeNatsMessage:
    def __init__(self, payload: dict[str, object] | bytes) -> None:
        self.data = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload
        self.headers: dict[str, str] = {}
        self.reply = "reply"
        self.response: dict[str, object] | list[dict[str, object]] | None = None

    async def respond(self, data: bytes) -> None:
        decoded = json.loads(data.decode("utf-8"))
        assert isinstance(decoded, (dict, list))
        self.response = decoded


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.mark.asyncio
async def test_current_profile_nats_handler_creates_profile(
    factory: sessionmaker[Session],
) -> None:
    server = UsersNatsServer(
        nats_url="nats://example.invalid:4222",
        subject="users.current_profile.v1",
        session_factory=factory,
    )
    message = FakeNatsMessage(
        {
            "authentik_subject": "ak-subject-nats",
            "email": "nats@example.test",
            "username": "nats-user",
        }
    )

    await server._handle_current_profile(message)

    assert isinstance(message.response, dict)
    assert isinstance(message.response["user"], dict)
    assert isinstance(message.response["consumer_profile"], dict)
    assert message.response["user"]["authentik_subject"] == "ak-subject-nats"
    assert message.response["consumer_profile"]["display_name"] == "nats-user"


@pytest.mark.asyncio
async def test_current_profile_nats_handler_rejects_invalid_payload(
    factory: sessionmaker[Session],
) -> None:
    server = UsersNatsServer(
        nats_url="nats://example.invalid:4222",
        subject="users.current_profile.v1",
        session_factory=factory,
    )
    message = FakeNatsMessage(b"not-json")

    await server._handle_current_profile(message)

    assert message.response == {"error": "invalid_request"}


@pytest.mark.asyncio
async def test_list_following_nats_handler(
    factory: sessionmaker[Session],
) -> None:
    # Seed data
    with factory() as session:
        from users.domain.models import ApplicationUser, ConsumerProfile, Follow, Page

        # Follower user
        follower = ApplicationUser(id="follower-123", username="follower_user")
        session.add(follower)

        # Target 1: Active user with a consumer profile (with display name)
        t_user_1 = ApplicationUser(id="user-idx-1", username="user1_uname")
        t_user_1.consumer_profile = ConsumerProfile(display_name="User One Display")
        session.add(t_user_1)

        # Target 2: Active user with no consumer profile display name (should fallback to username)
        t_user_2 = ApplicationUser(id="user-idx-2", username="user2_uname")
        session.add(t_user_2)

        # Target 3: Deleted or missing user (should fallback to target_handle)
        t_user_3 = ApplicationUser(id="user-idx-3", username="user3_uname", status="deleted")
        session.add(t_user_3)

        # Target 4: Page (club)
        t_page = Page(
            id="page-idx-1", slug="club-slug", display_name="Club Page Display", page_type="club"
        )
        session.add(t_page)

        # Create follows
        f1 = Follow(
            follower_user_id="follower-123",
            target_type="consumer",
            target_id="user-idx-1",
            target_handle="user1_uname",
        )
        f2 = Follow(
            follower_user_id="follower-123",
            target_type="artist",
            target_id="user-idx-2",
            target_handle="user2_uname",
        )
        f3 = Follow(
            follower_user_id="follower-123",
            target_type="consumer",
            target_id="user-idx-3",
            target_handle="user3_uname",
        )
        f4 = Follow(
            follower_user_id="follower-123",
            target_type="club",
            target_id="page-idx-1",
            target_handle="club-slug",
        )
        session.add_all([f1, f2, f3, f4])
        session.commit()

    server = UsersNatsServer(
        nats_url="nats://example.invalid:4222",
        subject="users.current_profile.v1",
        list_following_subject="users.follow.list_following.v1",
        session_factory=factory,
    )
    message = FakeNatsMessage({"user_id": "follower-123"})

    await server._handle_list_following(message)

    assert isinstance(message.response, list)
    assert len(message.response) == 4

    # Sort response by target_id to make assertions robust
    sorted_resp = sorted(message.response, key=lambda x: str(x["target_id"]))

    assert sorted_resp[0] == {
        "target_type": "page",
        "target_id": "page-idx-1",
        "target_handle": "club-slug",
        "display_name": "Club Page Display",
    }
    assert sorted_resp[1] == {
        "target_type": "consumer",
        "target_id": "user-idx-1",
        "target_handle": "user1_uname",
        "display_name": "User One Display",
    }
    assert sorted_resp[2] == {
        "target_type": "artist",
        "target_id": "user-idx-2",
        "target_handle": "user2_uname",
        "display_name": "user2_uname",
    }
    assert sorted_resp[3] == {
        "target_type": "consumer",
        "target_id": "user-idx-3",
        "target_handle": "user3_uname",
        "display_name": "user3_uname",  # deleted fallback to target_handle
    }


@pytest.mark.asyncio
async def test_list_following_rejects_invalid_payload(
    factory: sessionmaker[Session],
) -> None:
    server = UsersNatsServer(
        nats_url="nats://example.invalid:4222",
        subject="users.current_profile.v1",
        list_following_subject="users.follow.list_following.v1",
        session_factory=factory,
    )
    message = FakeNatsMessage(b"not-json")

    await server._handle_list_following(message)

    assert message.response == {"error": "invalid_request"}
