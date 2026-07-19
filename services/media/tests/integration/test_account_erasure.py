from fastapi.testclient import TestClient
from media.domain.models import MediaAsset, MediaDerivative
from media.main import app
from media.storage import InMemoryObjectStorage
from pytest import MonkeyPatch
from sqlalchemy.orm import Session

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}


def _asset(owner_user_id: str, suffix: str) -> MediaAsset:
    asset = MediaAsset(
        id=f"asset-{suffix}",
        owner_user_id=owner_user_id,
        context="user_avatar",
        bucket="threshold-media",
        original_key=f"assets/asset-{suffix}/original",
        content_type="image/png",
        size_bytes=10,
        status="ready",
    )
    asset.derivatives.append(
        MediaDerivative(
            id=f"derivative-{suffix}",
            variant="avatar_256",
            bucket=asset.bucket,
            object_key=f"assets/asset-{suffix}/avatar_256.webp",
            content_type="image/webp",
            size_bytes=5,
        )
    )
    return asset


def _store_asset_objects(storage: InMemoryObjectStorage, asset: MediaAsset) -> None:
    storage.put_object(
        bucket=asset.bucket,
        key=asset.original_key,
        body=b"original",
        content_type=asset.content_type,
    )
    for derivative in asset.derivatives:
        storage.put_object(
            bucket=derivative.bucket,
            key=derivative.object_key,
            body=b"derivative",
            content_type=derivative.content_type,
        )


def test_internal_account_erasure_deletes_owned_objects_and_records_idempotently(
    session: Session,
    object_storage: InMemoryObjectStorage,
) -> None:
    owned = _asset("user-1", "owned")
    retained = _asset("user-2", "retained")
    session.add_all([owned, retained])
    session.commit()
    _store_asset_objects(object_storage, owned)
    _store_asset_objects(object_storage, retained)
    owned_id = owned.id
    owned_bucket = owned.bucket
    owned_original_key = owned.original_key
    owned_derivative_key = owned.derivatives[0].object_key
    retained_id = retained.id
    retained_bucket = retained.bucket
    retained_original_key = retained.original_key

    client = TestClient(app)
    first = client.post(
        "/internal/v1/account-erasure",
        headers=TOKEN_HEADERS,
        json={"user_id": "user-1"},
    )
    second = client.post(
        "/internal/v1/account-erasure",
        headers=TOKEN_HEADERS,
        json={"user_id": "user-1"},
    )

    assert first.status_code == 200
    assert first.json() == {"status": "ok"}
    assert second.status_code == 200
    session.expire_all()
    assert session.get(MediaAsset, owned_id) is None
    assert session.get(MediaDerivative, "derivative-owned") is None
    assert session.get(MediaAsset, retained_id) is not None
    assert (owned_bucket, owned_original_key) not in object_storage.objects
    assert (owned_bucket, owned_derivative_key) not in object_storage.objects
    assert (retained_bucket, retained_original_key) in object_storage.objects


def test_internal_account_erasure_keeps_records_when_storage_delete_fails(
    session: Session,
    object_storage: InMemoryObjectStorage,
    monkeypatch: MonkeyPatch,
) -> None:
    owned = _asset("user-1", "failure")
    session.add(owned)
    session.commit()
    _store_asset_objects(object_storage, owned)

    def fail_delete(*, bucket: str, key: str) -> None:
        raise RuntimeError(f"storage unavailable for {bucket}/{key}")

    monkeypatch.setattr(object_storage, "delete_object", fail_delete)
    response = TestClient(app).post(
        "/internal/v1/account-erasure",
        headers=TOKEN_HEADERS,
        json={"user_id": "user-1"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "media storage unavailable"}
    session.expire_all()
    assert session.get(MediaAsset, owned.id) is not None
    assert session.get(MediaAsset, owned.id).status == "ready"


def test_internal_account_erasure_requires_internal_token() -> None:
    response = TestClient(app).post(
        "/internal/v1/account-erasure",
        json={"user_id": "user-1"},
    )

    assert response.status_code == 401
