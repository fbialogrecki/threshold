from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from users.api import routes
from users.main import app
from users.media_client import MediaAssetValidationError


def _get_authenticated_client(
    session: Session, email: str, username: str
) -> tuple[TestClient, str]:
    client = TestClient(app)
    response = client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass123!",
            "display_name": username.capitalize(),
        },
    )
    assert response.status_code == 201
    return client, response.json()["user"]["id"]


def test_patch_me_profile_accepts_avatar_media_asset(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, user_id = _get_authenticated_client(session, "avatar@example.test", "avataruser")
    calls = []

    def _validate(
        _settings: Any, *, asset_id: str, owner_user_id: str, allowed_contexts: set[str]
    ) -> None:
        calls.append((asset_id, owner_user_id, allowed_contexts))

    monkeypatch.setattr(routes, "validate_avatar_asset", _validate)

    response = client.patch(
        "/v1/me/profile",
        json={"avatar_media_asset_id": "asset-avatar-1"},
    )

    assert response.status_code == 200
    assert response.json()["consumer_profile"]["avatar_media_asset_id"] == "asset-avatar-1"
    assert calls == [("asset-avatar-1", user_id, {"user_avatar"})]


def test_patch_me_profile_rejects_invalid_avatar_media_asset(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _user_id = _get_authenticated_client(
        session, "bad-avatar@example.test", "badavataruser"
    )

    def _validate(
        _settings: Any, *, asset_id: str, owner_user_id: str, allowed_contexts: set[str]
    ) -> None:
        raise MediaAssetValidationError("media asset owner mismatch")

    monkeypatch.setattr(routes, "validate_avatar_asset", _validate)

    response = client.patch(
        "/v1/me/profile",
        json={"avatar_media_asset_id": "asset-avatar-2"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "media asset owner mismatch"
