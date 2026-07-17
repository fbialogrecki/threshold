import pytest
from auth_gateway.settings import Settings
from pydantic import ValidationError


def test_internal_token_reads_existing_secret_environment_key(monkeypatch) -> None:
    monkeypatch.setenv("THRESHOLD_INTERNAL_TOKEN", "test-internal-token")

    settings = Settings()

    assert settings.threshold_internal_token is not None
    assert settings.threshold_internal_token.get_secret_value() == "test-internal-token"


def test_internal_token_is_hidden_from_settings_representations(monkeypatch) -> None:
    token = "token-that-must-never-appear"
    monkeypatch.setenv("THRESHOLD_INTERNAL_TOKEN", token)

    settings = Settings()

    assert token not in repr(settings)
    assert token not in str(settings)
    assert token not in repr(settings.model_dump())


def test_internal_token_is_optional_for_nats_transport(monkeypatch) -> None:
    monkeypatch.delenv("THRESHOLD_INTERNAL_TOKEN", raising=False)

    settings = Settings(users_transport="nats")

    assert settings.threshold_internal_token is None


def test_internal_token_is_required_for_http_transport(monkeypatch) -> None:
    monkeypatch.delenv("THRESHOLD_INTERNAL_TOKEN", raising=False)

    with pytest.raises(
        ValidationError, match="internal token is required for HTTP users transport"
    ):
        Settings(users_transport="http")
