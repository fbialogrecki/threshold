import pytest
from pydantic import ValidationError
from users.settings import Settings


def test_production_rejects_enabled_plaintext_smtp():
    with pytest.raises(ValidationError, match="plaintext SMTP is restricted"):
        Settings(environment="production", smtp_enabled=True, smtp_security="plaintext")


def test_production_allows_disabled_plaintext_smtp_for_safe_local_compatibility():
    settings = Settings(environment="production", smtp_enabled=False, smtp_security="plaintext")

    assert settings.smtp_security == "plaintext"


@pytest.mark.parametrize("timeout", [0, -1, 30.1])
def test_smtp_timeout_is_positive_and_bounded(timeout: float):
    with pytest.raises(ValidationError):
        Settings(smtp_timeout_seconds=timeout)


def test_smtp_security_rejects_legacy_boolean_values():
    with pytest.raises(ValidationError):
        Settings(smtp_security=True)
