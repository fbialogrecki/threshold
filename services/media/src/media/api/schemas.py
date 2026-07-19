from typing import Literal

from media.main_dependencies import settings
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountErasureRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=150)

    model_config = ConfigDict(extra="forbid")


class AccountErasureResponse(BaseModel):
    status: Literal["ok"] = "ok"


class MediaAssetCreate(BaseModel):
    context: str
    content_type: str
    size_bytes: int = Field(gt=0)
    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    client_object_key: str | None = Field(default=None, exclude=True)

    @field_validator("context")
    @classmethod
    def validate_context(_cls, value: str) -> str:
        if value not in settings.allowed_asset_contexts:
            raise ValueError("unsupported media asset context")
        return value

    @field_validator("content_type")
    @classmethod
    def validate_content_type(_cls, value: str) -> str:
        if value not in settings.allowed_image_content_types:
            raise ValueError("unsupported image content type")
        return value

    @field_validator("size_bytes")
    @classmethod
    def validate_size(_cls, value: int) -> int:
        if value > settings.max_image_bytes:
            raise ValueError("image is too large")
        return value


class MediaDerivativeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    variant: str
    object_key: str
    content_type: str
    width: int | None
    height: int | None
    size_bytes: int | None


class MediaAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_user_id: str
    context: str
    bucket: str
    original_key: str
    content_type: str
    size_bytes: int
    checksum_sha256: str | None
    status: str
    derivatives: list[MediaDerivativeRead]


class MediaAssetValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_user_id: str
    context: str
    status: str


class StorageConfigRead(BaseModel):
    bucket: str
    region: str
    endpoint_configured: bool
    path_style: bool
