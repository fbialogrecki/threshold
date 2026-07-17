from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator

from threshold_common.config import ServiceSettings


class Settings(ServiceSettings):
    service_name: str = "auth-gateway"
    authentik_issuer: str | None = None
    authentik_jwks_url: str | None = None
    authentik_audience: str | None = None
    users_base_url: str = "http://127.0.0.1:8001"
    users_timeout_seconds: float = 2.0
    users_transport: Literal["http", "nats"] = "http"
    threshold_internal_token: SecretStr | None = Field(
        default=None, validation_alias="THRESHOLD_INTERNAL_TOKEN"
    )
    nats_url: str = "nats://127.0.0.1:4222"
    users_current_profile_subject: str = "users.current_profile.v1"

    @model_validator(mode="after")
    def require_http_internal_token(self) -> Self:
        if self.users_transport == "http" and (
            self.threshold_internal_token is None
            or not self.threshold_internal_token.get_secret_value()
        ):
            raise ValueError("internal token is required for HTTP users transport")
        return self
