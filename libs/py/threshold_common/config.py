from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    service_name: str
    environment: str = "local"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_prefix="THRESHOLD_", extra="ignore")
