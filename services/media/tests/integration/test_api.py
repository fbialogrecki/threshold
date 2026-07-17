import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from media.domain.models import MediaAsset
from media.main import app
from media.main_dependencies import settings
from media.storage import InMemoryObjectStorage
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

TOKEN_HEADERS = {"X-Threshold-Internal-Token": "test-internal-token"}
USER_HEADERS = {
    **TOKEN_HEADERS,
    "X-Threshold-User-Id": "user-1",
}


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (20, 10), color=(250, 20, 40)).save(output, format="PNG")
    return output.getvalue()


def wide_png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (9000, 1), color=(250, 20, 40)).save(output, format="PNG")
    return output.getvalue()


def decompression_bomb_png_bytes() -> bytes:
    output = BytesIO()
    Image.new("1", (8_000, 6_000)).save(output, format="PNG")
    return output.getvalue()


def multipart_body_with_context_headers(
    boundary: str, extra_headers: list[tuple[str, str]]
) -> bytes:
    headers = "".join(f"{name}: {value}\r\n" for name, value in extra_headers)
    return (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="context"\r\n'
            f"{headers}\r\n"
            "post_image\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="photo.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + png_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )


def test_healthz() -> None:
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "media"}


def test_readyz_checks_database(session: Session) -> None:
    client = TestClient(app)
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "media"}


def test_create_media_asset_metadata_uses_backend_owned_s3_keys(session: Session) -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/assets",
        headers=USER_HEADERS,
        json={
            "context": "user_avatar",
            "content_type": "image/png",
            "size_bytes": 12345,
            "checksum_sha256": "a" * 64,
            "client_object_key": "../../evil.png",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["context"] == "user_avatar"
    assert payload["owner_user_id"] == "user-1"
    assert payload["bucket"] == "threshold-media"
    assert payload["original_key"].startswith(f"assets/{payload['id']}/")
    assert payload["original_key"] == f"assets/{payload['id']}/original"
    assert payload["derivatives"] == []


def test_create_media_asset_rejects_missing_user_and_unknown_context(session: Session) -> None:
    client = TestClient(app)

    missing_user = client.post(
        "/v1/assets",
        headers=TOKEN_HEADERS,
        json={"context": "user_avatar", "content_type": "image/png", "size_bytes": 1},
    )
    assert missing_user.status_code == 401

    unknown_context = client.post(
        "/v1/assets",
        headers=USER_HEADERS,
        json={"context": "post_photo", "content_type": "image/png", "size_bytes": 1},
    )
    assert unknown_context.status_code == 422


def test_internal_token_missing_config_fails_closed(session: Session) -> None:
    client = TestClient(app)
    settings.threshold_internal_token = None

    response = client.get("/v1/config/storage", headers=TOKEN_HEADERS)

    assert response.status_code == 503


def test_upload_media_asset_stores_original_and_webp_derivatives(
    session: Session, object_storage: InMemoryObjectStorage
) -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/assets/upload",
        headers=USER_HEADERS,
        data={"context": "post_image"},
        files={"file": ("photo.png", png_bytes(), "image/png")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["context"] == "post_image"
    assert payload["status"] == "ready"
    assert payload["original_key"] == f"assets/{payload['id']}/original"
    assert {item["variant"] for item in payload["derivatives"]} == {"post_1280", "post_480"}
    assert ("threshold-media", payload["original_key"]) in object_storage.objects
    assert ("threshold-media", f"assets/{payload['id']}/post_1280.webp") in object_storage.objects

    derivative_response = client.get(
        f"/media/assets/assets/{payload['id']}/post_1280.webp", headers=TOKEN_HEADERS
    )
    assert derivative_response.status_code == 200
    assert derivative_response.headers["content-type"] == "image/webp"
    assert derivative_response.content.startswith(b"RIFF")


def test_upload_storage_failure_deletes_prior_objects_and_rolls_back_asset(
    session: Session, object_storage: InMemoryObjectStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_put = object_storage.put_object
    put_count = 0

    def fail_second_put(*, bucket: str, key: str, body: bytes, content_type: str) -> None:
        nonlocal put_count
        put_count += 1
        if put_count == 2:
            raise ClientError({"Error": {"Code": "ServiceUnavailable"}}, "PutObject")
        original_put(bucket=bucket, key=key, body=body, content_type=content_type)

    monkeypatch.setattr(object_storage, "put_object", fail_second_put)

    response = TestClient(app).post(
        "/v1/assets/upload",
        headers=USER_HEADERS,
        data={"context": "post_image"},
        files={"file": ("photo.png", png_bytes(), "image/png")},
    )

    assert (response.status_code, response.json()) == (
        503,
        {"detail": "media storage unavailable"},
    )
    assert object_storage.objects == {}
    assert session.scalars(select(MediaAsset)).all() == []


def test_upload_cleanup_failure_does_not_mask_storage_error_or_stop_remaining_deletes(
    session: Session, object_storage: InMemoryObjectStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_put = object_storage.put_object
    original_delete = object_storage.delete_object
    put_count = 0
    delete_calls: list[str] = []

    def fail_second_put(*, bucket: str, key: str, body: bytes, content_type: str) -> None:
        nonlocal put_count
        put_count += 1
        if put_count == 2:
            raise ClientError({"Error": {"Code": "ServiceUnavailable"}}, "PutObject")
        original_put(bucket=bucket, key=key, body=body, content_type=content_type)

    def fail_first_delete(*, bucket: str, key: str) -> None:
        delete_calls.append(key)
        if len(delete_calls) == 1:
            raise ClientError({"Error": {"Code": "ServiceUnavailable"}}, "DeleteObject")
        original_delete(bucket=bucket, key=key)

    monkeypatch.setattr(object_storage, "put_object", fail_second_put)
    monkeypatch.setattr(object_storage, "delete_object", fail_first_delete)

    response = TestClient(app).post(
        "/v1/assets/upload",
        headers=USER_HEADERS,
        data={"context": "post_image"},
        files={"file": ("photo.png", png_bytes(), "image/png")},
    )

    assert (response.status_code, response.json()) == (
        503,
        {"detail": "media storage unavailable"},
    )
    assert len(delete_calls) == 2
    assert object_storage.objects == {}


def test_upload_commit_failure_deletes_all_objects_and_rolls_back_asset(
    session: Session, object_storage: InMemoryObjectStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    rollback_calls = 0
    original_rollback = Session.rollback

    def fail_commit(_session: Session) -> None:
        raise RuntimeError("injected commit failure")

    def record_rollback(db_session: Session) -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback(db_session)

    with monkeypatch.context() as patcher:
        patcher.setattr(Session, "commit", fail_commit)
        patcher.setattr(Session, "rollback", record_rollback)
        response = TestClient(app, raise_server_exceptions=False).post(
            "/v1/assets/upload",
            headers=USER_HEADERS,
            data={"context": "post_image"},
            files={"file": ("photo.png", png_bytes(), "image/png")},
        )

    assert response.status_code == 500
    assert rollback_calls == 1
    assert object_storage.objects == {}
    assert session.scalars(select(MediaAsset)).all() == []


def test_upload_cancellation_deletes_written_objects_and_rolls_back_asset(
    session: Session, object_storage: InMemoryObjectStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_put = object_storage.put_object
    put_count = 0

    def cancel_second_put(*, bucket: str, key: str, body: bytes, content_type: str) -> None:
        nonlocal put_count
        put_count += 1
        if put_count == 2:
            raise asyncio.CancelledError
        original_put(bucket=bucket, key=key, body=body, content_type=content_type)

    monkeypatch.setattr(object_storage, "put_object", cancel_second_put)

    # BaseHTTPMiddleware translates a cancellation escaping the endpoint into this
    # transport-level error; the assertions below verify the compensation still ran.
    with pytest.raises(RuntimeError, match="No response returned"):
        TestClient(app).post(
            "/v1/assets/upload",
            headers=USER_HEADERS,
            data={"context": "post_image"},
            files={"file": ("photo.png", png_bytes(), "image/png")},
        )

    assert object_storage.objects == {}
    assert session.scalars(select(MediaAsset)).all() == []


def test_upload_media_asset_accepts_file_before_context(
    session: Session, object_storage: InMemoryObjectStorage
) -> None:
    boundary = "field-order"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="photo.png"\r\n'
            "Content-Type: image/png\r\n\r\n"
        ).encode()
        + png_bytes()
        + (
            f"\r\n--{boundary}\r\n"
            'Content-Disposition: form-data; name="context"\r\n\r\n'
            "post_image\r\n"
            f"--{boundary}--\r\n"
        ).encode()
    )
    client = TestClient(app)

    response = client.post(
        "/v1/assets/upload",
        headers={
            **USER_HEADERS,
            "content-type": f"multipart/form-data; boundary={boundary}",
        },
        content=body,
    )

    assert response.status_code == 201
    assert response.json()["content_type"] == "image/png"


def test_upload_media_asset_rejects_mismatched_magic_bytes(
    session: Session, object_storage: InMemoryObjectStorage
) -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/assets/upload",
        headers=USER_HEADERS,
        data={"context": "user_avatar"},
        files={"file": ("not-a-png.png", b"not image", "image/png")},
    )

    assert response.status_code == 422
    assert object_storage.objects == {}


def test_upload_media_asset_rejects_excessive_dimensions(
    session: Session, object_storage: InMemoryObjectStorage
) -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/assets/upload",
        headers=USER_HEADERS,
        data={"context": "post_image"},
        files={"file": ("wide.png", wide_png_bytes(), "image/png")},
    )

    assert response.status_code == 422
    assert object_storage.objects == {}


def test_upload_rejects_declared_oversize_before_reading_body(
    session: Session, object_storage: InMemoryObjectStorage
) -> None:
    client = TestClient(app)
    settings.max_upload_bytes = 100

    response = client.post(
        "/v1/assets/upload",
        headers={
            **USER_HEADERS,
            "content-type": "multipart/form-data; boundary=upload",
            "content-length": "101",
        },
        content=b"not read",
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "upload is too large"}
    assert object_storage.objects == {}


def test_upload_rejects_stream_that_exceeds_cap_without_content_length(
    session: Session, object_storage: InMemoryObjectStorage, tmp_path: Path
) -> None:
    client = TestClient(app)
    settings.max_upload_bytes = 100
    settings.upload_temp_dir = str(tmp_path)

    def chunks():
        yield b"x" * 60
        yield b"y" * 41

    response = client.post(
        "/v1/assets/upload",
        headers={
            **USER_HEADERS,
            "content-type": "multipart/form-data; boundary=upload",
            "transfer-encoding": "chunked",
        },
        content=chunks(),
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "upload is too large"}
    assert object_storage.objects == {}
    assert list(tmp_path.iterdir()) == []


def test_upload_rejects_file_part_that_exceeds_image_cap(
    session: Session, object_storage: InMemoryObjectStorage, tmp_path: Path
) -> None:
    client = TestClient(app)
    settings.max_image_bytes = 10
    settings.upload_temp_dir = str(tmp_path)

    response = client.post(
        "/v1/assets/upload",
        headers=USER_HEADERS,
        data={"context": "post_image"},
        files={"file": ("large.png", b"x" * 11, "image/png")},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "image is too large"}
    assert object_storage.objects == {}
    assert list(tmp_path.iterdir()) == []


def test_upload_rejects_empty_and_malformed_requests_with_stable_errors(
    session: Session, object_storage: InMemoryObjectStorage
) -> None:
    client = TestClient(app)

    empty = client.post(
        "/v1/assets/upload",
        headers={**USER_HEADERS, "content-type": "multipart/form-data; boundary=upload"},
        content=b"",
    )
    malformed_length = client.post(
        "/v1/assets/upload",
        headers={
            **USER_HEADERS,
            "content-type": "multipart/form-data; boundary=upload",
            "content-length": "not-a-number",
        },
        content=b"x",
    )
    malformed_form = client.post(
        "/v1/assets/upload",
        headers={**USER_HEADERS, "content-type": "multipart/form-data; boundary=upload"},
        content=b"not multipart",
    )

    assert (empty.status_code, empty.json()) == (422, {"detail": "empty upload"})
    assert (malformed_length.status_code, malformed_length.json()) == (
        400,
        {"detail": "invalid content-length"},
    )
    assert (malformed_form.status_code, malformed_form.json()) == (
        400,
        {"detail": "invalid multipart upload"},
    )
    assert object_storage.objects == {}


@pytest.mark.parametrize(
    "extra_headers",
    [
        pytest.param([(f"X-Header-{index}", "x") for index in range(8)], id="header-count"),
        pytest.param([("X" * 101, "x")], id="header-name-bytes"),
        pytest.param([("X-Header", "x" * 4097)], id="header-value-bytes"),
    ],
)
def test_upload_rejects_independently_oversized_multipart_headers_with_stable_error(
    session: Session,
    object_storage: InMemoryObjectStorage,
    extra_headers: list[tuple[str, str]],
) -> None:
    boundary = "bounded-headers"
    response = TestClient(app).post(
        "/v1/assets/upload",
        headers={**USER_HEADERS, "content-type": f"multipart/form-data; boundary={boundary}"},
        content=multipart_body_with_context_headers(boundary, extra_headers),
    )

    assert (response.status_code, response.json()) == (
        400,
        {"detail": "invalid multipart upload"},
    )
    assert object_storage.objects == {}


def test_upload_accepts_multipart_headers_at_each_limit(
    session: Session, object_storage: InMemoryObjectStorage
) -> None:
    boundary = "header-boundaries"
    extra_headers = [(f"X-Header-{index}", "x") for index in range(6)]
    extra_headers.append(("X" * 100, "x" * 4096))

    response = TestClient(app).post(
        "/v1/assets/upload",
        headers={**USER_HEADERS, "content-type": f"multipart/form-data; boundary={boundary}"},
        content=multipart_body_with_context_headers(boundary, extra_headers),
    )

    assert response.status_code == 201


def test_upload_cleans_request_temp_files_after_success(
    session: Session, object_storage: InMemoryObjectStorage, tmp_path: Path
) -> None:
    client = TestClient(app)
    settings.upload_temp_dir = str(tmp_path)

    response = client.post(
        "/v1/assets/upload",
        headers=USER_HEADERS,
        data={"context": "post_image"},
        files={"file": ("photo.png", png_bytes(), "image/png")},
    )

    assert response.status_code == 201
    assert list(tmp_path.iterdir()) == []


def test_upload_rejects_decompression_bomb_pixel_count(
    session: Session, object_storage: InMemoryObjectStorage
) -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/assets/upload",
        headers=USER_HEADERS,
        data={"context": "post_image"},
        files={"file": ("bomb.png", decompression_bomb_png_bytes(), "image/png")},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "image dimensions are too large"}
    assert object_storage.objects == {}


def test_internal_asset_proxy_rejects_encoded_traversal(session: Session) -> None:
    client = TestClient(app)
    response = client.get("/media/assets/assets/%2e%2e/original", headers=TOKEN_HEADERS)

    assert response.status_code == 404


def test_create_media_asset_rejects_unsupported_content_type_and_size(session: Session) -> None:
    client = TestClient(app)

    unsupported_type = client.post(
        "/v1/assets",
        headers=USER_HEADERS,
        json={"context": "event_poster", "content_type": "image/gif", "size_bytes": 1},
    )
    assert unsupported_type.status_code == 422

    too_large = client.post(
        "/v1/assets",
        headers=USER_HEADERS,
        json={"context": "event_poster", "content_type": "image/jpeg", "size_bytes": 10_000_001},
    )
    assert too_large.status_code == 422


def test_internal_asset_metadata_returns_asset_for_validation(session: Session) -> None:
    client = TestClient(app)
    created = client.post(
        "/v1/assets",
        headers=USER_HEADERS,
        json={"context": "user_avatar", "content_type": "image/png", "size_bytes": 123},
    )
    assert created.status_code == 201
    asset_id = created.json()["id"]

    response = client.get(f"/internal/v1/assets/{asset_id}", headers=TOKEN_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == asset_id
    assert payload["owner_user_id"] == "user-1"
    assert payload["context"] == "user_avatar"
    assert payload["status"] == "pending_upload"
    assert "bucket" not in payload
    assert "original_key" not in payload
    assert "checksum_sha256" not in payload
    assert "derivatives" not in payload


def test_s3_runtime_config_is_not_exposed(session: Session) -> None:
    client = TestClient(app)
    response = client.get("/v1/config/storage", headers=TOKEN_HEADERS)
    assert response.status_code == 200
    assert response.json() == {
        "bucket": "threshold-media",
        "region": "us-east-1",
        "endpoint_configured": True,
        "path_style": True,
    }
