from pydantic import Field, field_validator

from threshold_common.config import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "social"
    database_url: str = "sqlite+pysqlite:///:memory:"

    nats_enabled: bool = False
    nats_url: str = "nats://127.0.0.1:4222"
    users_list_following_subject: str = "users.follow.list_following.v1"
    user_block_changed_subject: str = "users.block.changed.v1"
    users_service_url: str | None = Field(default=None, validation_alias="USERS_SERVICE_URL")
    events_service_url: str | None = Field(default=None, validation_alias="EVENTS_SERVICE_URL")
    media_service_url: str | None = None
    nats_request_timeout_seconds: float = 1.5
    media_request_timeout_seconds: float = 1.5
    # Repairs the local block copy if a users.block.changed event was lost.
    block_sync_interval_seconds: float = 300
    block_sync_timeout_seconds: float = 10

    threshold_internal_token: str | None = Field(
        default=None, validation_alias="THRESHOLD_INTERNAL_TOKEN"
    )

    default_feed_limit: int = 30
    max_feed_limit: int = 100
    max_post_body_length: int = 2000
    max_comment_body_length: int = 1000
    write_rate_limit_count: int = 60
    write_rate_limit_window_seconds: int = 60

    @field_validator("database_url")
    @classmethod
    def prefer_psycopg_driver(_cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value
