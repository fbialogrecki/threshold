from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from threshold_common.config import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "users"
    database_url: str = "sqlite+pysqlite:///:memory:"
    nats_enabled: bool = False
    nats_url: str = "nats://127.0.0.1:4222"
    users_current_profile_subject: str = "users.current_profile.v1"
    users_list_following_subject: str = "users.follow.list_following.v1"
    user_block_changed_subject: str = "users.block.changed.v1"
    social_service_url: str | None = None
    events_service_url: str | None = None
    media_service_url: str | None = None
    threshold_internal_token: str | None = Field(
        default=None, validation_alias="THRESHOLD_INTERNAL_TOKEN"
    )
    social_request_timeout_seconds: float = 1.5
    events_request_timeout_seconds: float = 1.5
    media_request_timeout_seconds: float = 1.5
    account_erasure_worker_enabled: bool = True
    account_erasure_poll_seconds: float = Field(default=10.0, gt=0)
    account_erasure_lease_seconds: int = Field(default=120, ge=10)

    auth_password_pepper_current: str = "dev-only-users-password-pepper-change-me"
    auth_password_pepper_previous: str | None = None
    auth_password_pepper_version: int = 1
    auth_session_token_hmac_key: str = "dev-only-users-session-hmac-key-change-me"
    auth_audit_hash_key: str = "dev-only-users-audit-hash-key-change-me"
    auth_cookie_secure: bool = False
    auth_dev_expose_tokens: bool = False
    auth_rate_limit_count: int = 120
    auth_rate_limit_window_seconds: int = 60
    auth_session_ttl_minutes: int = 15
    auth_refresh_ttl_days: int = 30
    auth_email_verification_ttl_hours: int = 24
    auth_password_reset_ttl_minutes: int = 30

    smtp_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_security: Literal["starttls", "implicit_tls", "plaintext"] = "plaintext"
    smtp_timeout_seconds: float = Field(default=10.0, gt=0, le=30)
    smtp_ca_file: str | None = None
    smtp_from: str = "no-reply@example.test"
    web_host: str = "127.0.0.1:3000"

    @model_validator(mode="after")
    def restrict_plaintext_smtp(self) -> Self:
        if (
            self.smtp_enabled
            and self.smtp_security == "plaintext"
            and self.environment.lower() not in {"local", "test"}
        ):
            raise ValueError("plaintext SMTP is restricted to local and test environments")
        return self

    @field_validator("database_url")
    @classmethod
    def prefer_psycopg_driver(_cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value
