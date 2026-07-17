# mypy: disable-error-code=no-untyped-def
import logging
import smtplib
from unittest.mock import MagicMock, call, patch

from sqlalchemy.orm import Session
from users.auth.service import (
    _send_email,
    register_user,
    request_email_verification,
    request_password_reset,
)
from users.settings import Settings

RECIPIENT = "private-recipient@example.com"
SUBJECT = "Private subject"
BODY = "https://app.example.test/reset-password?token=secret-token"


def _smtp_settings(**overrides) -> Settings:
    values = {
        "smtp_enabled": True,
        "smtp_host": "mail.example.com",
        "smtp_port": 587,
        "smtp_username": "smtp-user",
        "smtp_password": "smtp-password",
        "smtp_security": "starttls",
        "smtp_timeout_seconds": 8.0,
        "smtp_from": "no-reply@example.com",
        "web_host": "app.example.test",
        "auth_audit_hash_key": "test-email-log-key",
    }
    values.update(overrides)
    return Settings(**values)


def _send(settings: Settings) -> None:
    _send_email(settings, recipient=RECIPIENT, subject=SUBJECT, body=BODY)


def test_send_email_disabled_logs_only_keyed_recipient_id(caplog):
    caplog.set_level(logging.INFO)
    settings = _smtp_settings(smtp_enabled=False)

    with patch("users.auth.service.smtplib.SMTP") as mock_smtp:
        _send(settings)

    mock_smtp.assert_not_called()
    assert "email_delivery_disabled" in caplog.text
    assert "recipient_id=" in caplog.text
    assert RECIPIENT not in caplog.text
    assert SUBJECT not in caplog.text
    assert BODY not in caplog.text
    assert "secret-token" not in caplog.text


def test_starttls_requires_extension_and_reissues_ehlo_after_tls():
    settings = _smtp_settings(smtp_ca_file="/etc/ssl/private-smtp-ca.pem")

    with (
        patch("users.auth.service.ssl.create_default_context") as create_context,
        patch("users.auth.service.smtplib.SMTP") as mock_smtp,
    ):
        context = MagicMock(name="verified-tls-context")
        create_context.return_value = context
        server = MagicMock()
        server.has_extn.return_value = True
        mock_smtp.return_value.__enter__.return_value = server

        _send(settings)

    create_context.assert_called_once_with(cafile="/etc/ssl/private-smtp-ca.pem")
    mock_smtp.assert_called_once_with("mail.example.com", 587, timeout=8.0)
    assert server.method_calls[:4] == [
        call.ehlo(),
        call.has_extn("starttls"),
        call.starttls(context=context),
        call.ehlo(),
    ]
    server.login.assert_called_once_with("smtp-user", "smtp-password")
    server.send_message.assert_called_once()


def test_starttls_missing_extension_never_downgrades(caplog):
    caplog.set_level(logging.ERROR)
    settings = _smtp_settings()

    with patch("users.auth.service.smtplib.SMTP") as mock_smtp:
        server = MagicMock()
        server.has_extn.return_value = False
        mock_smtp.return_value.__enter__.return_value = server

        _send(settings)

    server.starttls.assert_not_called()
    server.login.assert_not_called()
    server.send_message.assert_not_called()
    assert "email_delivery_failed" in caplog.text
    assert "category=tls_unavailable" in caplog.text
    assert RECIPIENT not in caplog.text


def test_implicit_tls_uses_smtp_ssl_with_verified_context():
    settings = _smtp_settings(smtp_security="implicit_tls", smtp_port=465, smtp_ca_file=None)

    with (
        patch("users.auth.service.ssl.create_default_context") as create_context,
        patch("users.auth.service.smtplib.SMTP") as mock_smtp,
        patch("users.auth.service.smtplib.SMTP_SSL") as mock_smtp_ssl,
    ):
        context = MagicMock(name="verified-tls-context")
        create_context.return_value = context
        server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = server

        _send(settings)

    create_context.assert_called_once_with(cafile=None)
    mock_smtp.assert_not_called()
    mock_smtp_ssl.assert_called_once_with(
        "mail.example.com", 465, timeout=8.0, context=context
    )
    server.login.assert_called_once_with("smtp-user", "smtp-password")
    server.send_message.assert_called_once()


def test_plaintext_is_available_for_local_test_smtp():
    settings = _smtp_settings(
        environment="test",
        smtp_security="plaintext",
        smtp_username=None,
        smtp_password=None,
    )

    with (
        patch("users.auth.service.ssl.create_default_context") as create_context,
        patch("users.auth.service.smtplib.SMTP") as mock_smtp,
    ):
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server

        _send(settings)

    create_context.assert_not_called()
    mock_smtp.assert_called_once_with("mail.example.com", 587, timeout=8.0)
    server.starttls.assert_not_called()
    server.login.assert_not_called()
    server.send_message.assert_called_once()


def test_smtp_failure_log_excludes_message_fields_credentials_and_exception(caplog):
    caplog.set_level(logging.ERROR)
    exception_secret = "provider leaked smtp-password and secret-token"
    settings = _smtp_settings()

    with patch("users.auth.service.smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = smtplib.SMTPException(exception_secret)
        _send(settings)

    assert "email_delivery_failed" in caplog.text
    assert "category=smtp_protocol" in caplog.text
    assert "recipient_id=" in caplog.text
    for secret in (
        RECIPIENT,
        SUBJECT,
        BODY,
        "smtp-user",
        "smtp-password",
        "secret-token",
        exception_secret,
        "Traceback",
    ):
        assert secret not in caplog.text


def test_registration_triggers_email(session: Session):
    settings = Settings(smtp_enabled=False, web_host="app.example.test")

    with patch("users.auth.service._send_email") as mock_send:
        register_user(
            session=session,
            settings=settings,
            email="new@example.com",
            username="newuser",
            password="StrongPass123!",
            display_name="New User",
        )

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs["recipient"] == "new@example.com"
        assert kwargs["subject"] == "Verify your email address"
        assert "/verify-email?token=" in kwargs["body"]


def test_request_verification_triggers_email(session: Session):
    settings = Settings(smtp_enabled=False, web_host="app.example.test")
    user, _, _, _ = register_user(
        session=session,
        settings=settings,
        email="verify@example.com",
        username="verifyuser",
        password="StrongPass123!",
        display_name="Verify User",
    )

    with patch("users.auth.service._send_email") as mock_send:
        request_email_verification(session=session, settings=settings, user=user)

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs["recipient"] == "verify@example.com"
        assert kwargs["subject"] == "Verify your email address"
        assert "/verify-email?token=" in kwargs["body"]


def test_request_password_reset_triggers_email(session: Session):
    settings = Settings(smtp_enabled=False, web_host="app.example.test")
    register_user(
        session=session,
        settings=settings,
        email="reset@example.com",
        username="resetuser",
        password="StrongPass123!",
        display_name="Reset User",
    )

    with patch("users.auth.service._send_email") as mock_send:
        request_password_reset(session=session, settings=settings, email="reset@example.com")

        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs["recipient"] == "reset@example.com"
        assert kwargs["subject"] == "Reset your password"
        assert "/reset-password?token=" in kwargs["body"]
