import pytest
from fastapi.testclient import TestClient
from social.main import app
from sqlalchemy.orm import Session

USER_HEADERS = {
    "X-Threshold-Internal-Token": "test-internal-token",
    "X-Threshold-User-Id": "user-1",
    "X-Threshold-Username": "nightcrawler",
    "X-Threshold-Display-Name": "Night Crawler",
}


def test_post_can_reference_uploaded_images(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from social import media_client

    def _valid_post_image_asset(_settings: object, *, asset_id: str, owner_user_id: str) -> None:
        assert owner_user_id == "user-1"
        assert asset_id in {"asset-1", "asset-2"}

    monkeypatch.setattr(media_client, "validate_post_image_asset", _valid_post_image_asset)
    client = TestClient(app)
    assert (
        client.post("/v1/groups/techno-warsaw/membership", headers=USER_HEADERS).status_code
        == 200
    )

    response = client.post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={
            "group_slug": "techno-warsaw",
            "body": "photo from the floor",
            "media_asset_ids": ["asset-1", "asset-2"],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["media_asset_ids"] == ["asset-1", "asset-2"]


def test_post_rejects_invalid_media_asset_without_persisting(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from social.domain.models import Post

    from social import media_client

    def _invalid_asset(*_args: object, **_kwargs: object) -> None:
        raise media_client.MediaAssetValidationError("media asset context mismatch")

    monkeypatch.setattr(media_client, "validate_post_image_asset", _invalid_asset)
    response = TestClient(app).post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "bad image ref", "media_asset_ids": ["event-poster-asset"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid post media asset"
    assert session.query(Post).filter_by(body="bad image ref").one_or_none() is None


def test_post_fails_closed_when_media_validation_is_not_configured(session: Session) -> None:
    from social.domain.models import Post

    response = TestClient(app).post(
        "/v1/posts",
        headers=USER_HEADERS,
        json={"body": "unconfigured media validation", "media_asset_ids": ["asset-1"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid post media asset"
    assert session.query(Post).filter_by(body="unconfigured media validation").one_or_none() is None
