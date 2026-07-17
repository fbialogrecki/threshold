from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from urllib.parse import unquote

from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from media.api.schemas import (
    MediaAssetCreate,
    MediaAssetRead,
    MediaAssetValidationRead,
    StorageConfigRead,
)
from media.api.security import require_internal_token, require_user_id
from media.domain.models import MediaAsset, MediaDerivative
from media.images import InvalidImageError, process_image
from media.main_dependencies import get_object_storage, get_session, settings
from media.storage import ObjectStorage
from media.uploads import parse_multipart_upload, stream_request_to_file, validate_content_length
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

router = APIRouter()


def _safe_asset_path(asset_path: str) -> bool:
    if not asset_path.startswith("assets/"):
        return False
    segments = asset_path.split("/")
    return all(unquote(segment) not in {".", ".."} for segment in segments)


def _create_asset_record(
    *,
    owner_user_id: str,
    context: str,
    content_type: str,
    size_bytes: int,
    checksum_sha256: str | None,
    session: Session,
) -> MediaAsset:
    asset = MediaAsset(
        owner_user_id=owner_user_id,
        context=context,
        bucket=settings.s3_bucket,
        original_key="",
        content_type=content_type,
        size_bytes=size_bytes,
        checksum_sha256=checksum_sha256,
    )
    session.add(asset)
    session.flush()
    asset.original_key = f"assets/{asset.id}/original"
    return asset


@router.post(
    "/v1/assets",
    response_model=MediaAssetRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_token)],
)
def create_asset(
    payload: MediaAssetCreate,
    owner_user_id: Annotated[str, Depends(require_user_id)],
    session: Annotated[Session, Depends(get_session)],
) -> MediaAsset:
    asset = _create_asset_record(
        owner_user_id=owner_user_id,
        context=payload.context,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        checksum_sha256=payload.checksum_sha256,
        session=session,
    )
    session.commit()
    session.refresh(asset)
    return asset


@router.post(
    "/v1/assets/upload",
    response_model=MediaAssetRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_token)],
)
async def upload_asset(
    request: Request,
    owner_user_id: Annotated[str, Depends(require_user_id)],
    session: Annotated[Session, Depends(get_session)],
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> MediaAsset:
    validate_content_length(request, settings.max_upload_bytes)
    with TemporaryDirectory(dir=settings.upload_temp_dir, prefix="media-upload-") as temp_dir:
        request_path = Path(temp_dir) / "request.multipart"
        image_path = Path(temp_dir) / "image"
        with request_path.open("w+b") as request_file:
            await stream_request_to_file(request, request_file, settings.max_upload_bytes)
            upload = parse_multipart_upload(
                request_file,
                image_path,
                request.headers.get("content-type"),
                settings.max_image_bytes,
            )

        if upload.context not in settings.allowed_asset_contexts:
            raise HTTPException(status_code=422, detail="unsupported media asset context")
        if upload.content_type not in settings.allowed_image_content_types:
            raise HTTPException(status_code=422, detail="unsupported image content type")
        try:
            processed = process_image(upload.file_path, upload.content_type, upload.context)
        except InvalidImageError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        asset = _create_asset_record(
            owner_user_id=owner_user_id,
            context=upload.context,
            content_type=processed.content_type,
            size_bytes=upload.size_bytes,
            checksum_sha256=None,
            session=session,
        )
        try:
            with upload.file_path.open("rb") as original:
                storage.put_object(
                    bucket=asset.bucket,
                    key=asset.original_key,
                    body=original,
                    content_type=processed.content_type,
                )
            for variant, derivative_body in processed.derivatives.items():
                object_key = f"assets/{asset.id}/{variant}.webp"
                storage.put_object(
                    bucket=asset.bucket,
                    key=object_key,
                    body=derivative_body,
                    content_type="image/webp",
                )
                session.add(
                    MediaDerivative(
                        asset_id=asset.id,
                        variant=variant,
                        bucket=asset.bucket,
                        object_key=object_key,
                        content_type="image/webp",
                        size_bytes=len(derivative_body),
                    )
                )
        except ClientError as exc:
            raise HTTPException(status_code=503, detail="media storage unavailable") from exc
        asset.status = "ready"
        session.commit()
        loaded_asset = session.get(
            MediaAsset,
            asset.id,
            options=[selectinload(MediaAsset.derivatives)],
        )
        if loaded_asset is None:
            raise HTTPException(status_code=500, detail="asset not found after upload")
        return loaded_asset


@router.get(
    "/v1/config/storage",
    response_model=StorageConfigRead,
    dependencies=[Depends(require_internal_token)],
)
def storage_config() -> StorageConfigRead:
    return StorageConfigRead(
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        endpoint_configured=bool(settings.s3_endpoint_url),
        path_style=settings.s3_path_style,
    )


@router.get(
    "/internal/v1/assets/{asset_id}",
    response_model=MediaAssetValidationRead,
    dependencies=[Depends(require_internal_token)],
)
def read_asset_metadata(
    asset_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> MediaAsset:
    asset = session.scalar(
        select(MediaAsset)
        .where(MediaAsset.id == asset_id)
        .options(selectinload(MediaAsset.derivatives))
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset


@router.get("/media/assets/{asset_path:path}", dependencies=[Depends(require_internal_token)])
def read_asset_object(
    asset_path: str,
    storage: Annotated[ObjectStorage, Depends(get_object_storage)],
) -> Response:
    if not _safe_asset_path(asset_path):
        raise HTTPException(status_code=404, detail="asset not found")
    try:
        body, content_type = storage.get_object(bucket=settings.s3_bucket, key=asset_path)
    except KeyError:
        raise HTTPException(status_code=404, detail="asset not found") from None
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
            raise HTTPException(status_code=404, detail="asset not found") from exc
        raise HTTPException(status_code=503, detail="media storage unavailable") from exc
    return Response(content=body, media_type=content_type)
