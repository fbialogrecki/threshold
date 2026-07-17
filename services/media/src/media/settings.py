from pydantic import Field, field_validator

from threshold_common.config import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "media"
    database_url: str = "sqlite+pysqlite:///:memory:"

    threshold_internal_token: str | None = Field(
        default=None, validation_alias="THRESHOLD_INTERNAL_TOKEN"
    )

    s3_endpoint_url: str = Field(
        default="http://127.0.0.1:8333",
        validation_alias="MEDIA_S3_ENDPOINT_URL",
    )
    s3_bucket: str = Field(default="threshold-media", validation_alias="MEDIA_S3_BUCKET")
    s3_region: str = Field(default="us-east-1", validation_alias="MEDIA_S3_REGION")
    s3_path_style: bool = Field(default=True, validation_alias="MEDIA_S3_PATH_STYLE")
    s3_access_key_id: str | None = Field(default=None, validation_alias="MEDIA_S3_ACCESS_KEY_ID")
    s3_secret_access_key: str | None = Field(
        default=None, validation_alias="MEDIA_S3_SECRET_ACCESS_KEY"
    )

    max_image_bytes: int = 10_000_000
    # Includes bounded multipart framing while preserving the 10 MB image limit.
    max_upload_bytes: int = 10_100_000
    upload_temp_dir: str | None = None
    allowed_image_content_types: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")
    allowed_asset_contexts: tuple[str, ...] = (
        "user_avatar",
        "page_avatar",
        "post_image",
        "event_poster",
    )

    @field_validator("database_url")
    @classmethod
    def prefer_psycopg_driver(_cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value
