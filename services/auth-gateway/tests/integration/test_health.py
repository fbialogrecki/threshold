from dataclasses import dataclass

import auth_gateway.main as main
from auth_gateway.main import app
from fastapi.testclient import TestClient

from threshold_common.auth import Principal


def test_healthz() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "auth-gateway"}


def test_me_requires_bearer_token() -> None:
    client = TestClient(app)
    response = client.get("/me")
    assert response.status_code == 401


def test_me_fails_closed_when_auth_validation_is_not_configured() -> None:
    client = TestClient(app)
    response = client.get("/me", headers={"Authorization": "Bearer smoke"})
    assert response.status_code == 503
    assert response.json() == {"detail": "auth validation is not configured"}


@dataclass
class FakeJwtVerifier:
    def verify(self, token: str) -> Principal:
        assert token == "smoke"
        return Principal(subject="ak-subject", email="ada@example.test", username="ada")


@dataclass
class FakeUsersProfileClient:
    async def current_profile(
        self,
        *,
        subject: str,
        email: str | None,
        username: str | None,
    ) -> dict[str, object]:
        assert subject == "ak-subject"
        assert email == "ada@example.test"
        assert username == "ada"
        return {
            "user": {
                "id": "user-1",
                "authentik_subject": subject,
                "email": email,
                "username": username,
            },
            "consumer_profile": {
                "id": "profile-1",
                "display_name": "Ada",
                "bio": None,
            },
            "onboarding_preferences": {
                "id": "prefs-1",
                "city": "Wroclaw",
                "preferred_scenes": "electronic,live",
            },
        }


def test_main_passes_internal_token_without_changing_nats_transport(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("THRESHOLD_INTERNAL_TOKEN", "test-internal-token")
    monkeypatch.setattr(
        main,
        "UsersProfileClient",
        lambda **kwargs: captured.update(kwargs) or FakeUsersProfileClient(),
    )

    main._build_users_profile_client(main.Settings(users_transport="nats"))

    assert captured["transport"] == "nats"
    assert captured["internal_token"] == "test-internal-token"


def test_me_returns_application_profile_from_users(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(main, "jwt_verifier", FakeJwtVerifier())
    monkeypatch.setattr(main, "users_profile_client", FakeUsersProfileClient(), raising=False)
    client = TestClient(app)

    response = client.get("/me", headers={"Authorization": "Bearer smoke"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "authenticated",
        "subject": "ak-subject",
        "email": "ada@example.test",
        "username": "ada",
        "profile": {
            "user": {
                "id": "user-1",
                "authentik_subject": "ak-subject",
                "email": "ada@example.test",
                "username": "ada",
            },
            "consumer_profile": {
                "id": "profile-1",
                "display_name": "Ada",
                "bio": None,
            },
            "onboarding_preferences": {
                "id": "prefs-1",
                "city": "Wroclaw",
                "preferred_scenes": "electronic,live",
            },
        },
    }
