from pydantic import Field, field_validator

from threshold_common.config import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "events"
    database_url: str = "sqlite+pysqlite:///:memory:"

    users_base_url: str = "http://127.0.0.1:8001"
    media_service_url: str | None = None
    social_service_url: str | None = None
    media_request_timeout_seconds: float = 1.5

    default_list_limit: int = 30
    max_list_limit: int = 100

    write_rate_limit_count: int = 60
    write_rate_limit_window_seconds: int = 60
    check_in_token_ttl_seconds: int = 300

    threshold_internal_token: str | None = Field(
        default=None, validation_alias="THRESHOLD_INTERNAL_TOKEN"
    )

    @field_validator("database_url")
    @classmethod
    def prefer_psycopg_driver(_cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value
