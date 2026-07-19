from io import BytesIO
from typing import cast
from unittest.mock import Mock

from fastapi.testclient import TestClient
from media.api.routes import _acquire_owner_write_lock
from media.domain.models import AccountErasureTombstone, MediaAsset, MediaDerivative
from media.main import app
from media.storage import InMemoryObjectStorage
from PIL import Image
from pytest import MonkeyPatch
from sqlalchemy.orm import Session

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
USER_HEADERS = {**TOKEN_HEADERS, "X-Threshold-User-Id": "user-1"}


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (20, 10), color=(250, 20, 40)).save(output, format="PNG")
    return output.getvalue()


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


def test_postgresql_owner_fence_uses_transaction_scoped_service_lock() -> None:
    session = Mock()
    session.get_bind.return_value.dialect.name = "postgresql"

    _acquire_owner_write_lock(owner_user_id="user-1", session=cast(Session, session))

    statement, parameters = session.execute.call_args.args
    assert str(statement) == (
        "SELECT pg_advisory_xact_lock(hashtextextended(:owner, :seed))"
    )
    assert parameters == {"owner": "user-1", "seed": 42002}


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
    assert session.get(AccountErasureTombstone, "user-1") is not None
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
    assert session.get(AccountErasureTombstone, "user-1") is not None


def test_tombstone_rejects_metadata_create_and_upload_without_writing_objects(
    session: Session,
    object_storage: InMemoryObjectStorage,
) -> None:
    session.add(AccountErasureTombstone(owner_user_id="user-1"))
    session.commit()

    client = TestClient(app)
    create_response = client.post(
        "/v1/assets",
        headers=USER_HEADERS,
        json={"context": "user_avatar", "content_type": "image/png", "size_bytes": 10},
    )
    upload_response = client.post(
        "/v1/assets/upload",
        headers=USER_HEADERS,
        data={"context": "user_avatar"},
        files={"file": ("photo.png", _png_bytes(), "image/png")},
    )

    assert (create_response.status_code, create_response.json()) == (
        409,
        {"detail": "account media erasure has started"},
    )
    assert (upload_response.status_code, upload_response.json()) == (
        409,
        {"detail": "account media erasure has started"},
    )
    assert object_storage.objects == {}
    assert session.query(MediaAsset).count() == 0


def test_account_erasure_retries_after_partial_delete_and_treats_missing_keys_as_success(
    session: Session,
    object_storage: InMemoryObjectStorage,
    monkeypatch: MonkeyPatch,
) -> None:
    owned = _asset("user-1", "retry")
    session.add(owned)
    session.commit()
    _store_asset_objects(object_storage, owned)
    owned_id = owned.id
    bucket = owned.bucket
    original_key = owned.original_key
    derivative_key = owned.derivatives[0].object_key
    original_delete = object_storage.delete_object
    delete_calls = 0

    def fail_second_delete(*, bucket: str, key: str) -> None:
        nonlocal delete_calls
        delete_calls += 1
        if delete_calls == 2:
            raise RuntimeError("storage unavailable")
        original_delete(bucket=bucket, key=key)

    with monkeypatch.context() as patcher:
        patcher.setattr(object_storage, "delete_object", fail_second_delete)
        first = TestClient(app).post(
            "/internal/v1/account-erasure",
            headers=TOKEN_HEADERS,
            json={"user_id": "user-1"},
        )

    assert first.status_code == 503
    assert (bucket, original_key) not in object_storage.objects
    assert (bucket, derivative_key) in object_storage.objects
    session.expire_all()
    assert session.get(AccountErasureTombstone, "user-1") is not None
    assert session.get(MediaAsset, owned_id) is not None

    def raise_for_missing(*, bucket: str, key: str) -> None:
        if (bucket, key) not in object_storage.objects:
            raise KeyError(key)
        original_delete(bucket=bucket, key=key)

    with monkeypatch.context() as patcher:
        patcher.setattr(object_storage, "delete_object", raise_for_missing)
        retry = TestClient(app).post(
            "/internal/v1/account-erasure",
            headers=TOKEN_HEADERS,
            json={"user_id": "user-1"},
        )

    assert retry.status_code == 200
    session.expire_all()
    assert session.get(MediaAsset, owned_id) is None
    assert session.get(AccountErasureTombstone, "user-1") is not None
    assert (bucket, derivative_key) not in object_storage.objects


def test_internal_account_erasure_requires_internal_token() -> None:
    response = TestClient(app).post(
        "/internal/v1/account-erasure",
        json={"user_id": "user-1"},
    )

    assert response.status_code == 401
