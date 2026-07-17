import logging
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from users.auth.hashing import (
    PasswordHashResult,
    PasswordPolicyError,
    hash_password,
    verify_password,
)
from users.auth.tokens import generate_opaque_token, keyed_hash, stable_hash
from users.domain.models import (
    ApplicationUser,
    AuthAuditLog,
    ConsumerProfile,
    EmailVerificationToken,
    IdentitySource,
    OnboardingPreferences,
    PasswordResetToken,
    UserCredential,
    UserSession,
    utc_now,
)
from users.settings import Settings

logger = logging.getLogger(__name__)


class _StartTLSUnavailableError(smtplib.SMTPException):
    pass


def _email_recipient_id(settings: Settings, recipient: str) -> str:
    return keyed_hash(normalize_email(recipient), settings.auth_audit_hash_key)[:16]


def _smtp_error_category(exc: Exception) -> str:
    if isinstance(exc, _StartTLSUnavailableError):
        return "tls_unavailable"
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "authentication"
    if isinstance(exc, ssl.SSLError):
        return "tls_verification"
    if isinstance(exc, smtplib.SMTPException):
        return "smtp_protocol"
    if isinstance(exc, (TimeoutError, OSError)):
        return "network"
    return "unexpected"


def _deliver_smtp(settings: Settings, message: EmailMessage) -> None:
    context = (
        ssl.create_default_context(cafile=settings.smtp_ca_file)
        if settings.smtp_security != "plaintext"
        else None
    )
    server_context: smtplib.SMTP
    if settings.smtp_security == "implicit_tls":
        server_context = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
            context=context,
        )
    else:
        server_context = smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        )

    with server_context as server:
        if settings.smtp_security == "starttls":
            server.ehlo()
            if not server.has_extn("starttls"):
                raise _StartTLSUnavailableError
            server.starttls(context=context)
            server.ehlo()
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def _send_email(settings: Settings, recipient: str, subject: str, body: str) -> None:
    recipient_id = _email_recipient_id(settings, recipient)
    if not settings.smtp_enabled:
        logger.info("email_delivery_disabled recipient_id=%s", recipient_id)
        return

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = recipient
        msg.set_content(body)
        _deliver_smtp(settings, msg)
        logger.info("email_delivery_succeeded recipient_id=%s", recipient_id)
    except Exception as exc:
        logger.error(
            "email_delivery_failed recipient_id=%s category=%s",
            recipient_id,
            _smtp_error_category(exc),
        )


class AuthError(ValueError):
    pass


class DuplicateIdentityError(AuthError):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_username(username: str) -> str:
    return username.strip().lower()


def _hash_token(token: str, settings: Settings) -> str:
    return keyed_hash(token, settings.auth_session_token_hmac_key)


_DUMMY_LOGIN_PASSWORD = "DummyPassword123!"
_dummy_login_hash: str | None = None


def _dummy_verify_password(settings: Settings, password: str) -> None:
    global _dummy_login_hash
    if _dummy_login_hash is None:
        _dummy_login_hash = hash_password(
            _DUMMY_LOGIN_PASSWORD,
            pepper="dummy-login-pepper",
            pepper_version=0,
        ).encoded_hash
    verify_password(password, _dummy_login_hash, pepper=settings.auth_password_pepper_current)


def _is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=utc_now().tzinfo)
    return bool(expires_at <= utc_now())


def _audit_hash(value: str | None, settings: Settings) -> str | None:
    return stable_hash(value, settings.auth_audit_hash_key)


def audit(
    session: Session,
    settings: Settings,
    *,
    event_type: str,
    result: str,
    user_id: str | None = None,
    subject: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, str | int | bool | None] | None = None,
) -> None:
    session.add(
        AuthAuditLog(
            user_id=user_id,
            event_type=event_type,
            result=result,
            subject_hash=_audit_hash(subject, settings),
            ip_hash=_audit_hash(ip, settings),
            user_agent_hash=_audit_hash(user_agent, settings),
            metadata_json=metadata or {},
        )
    )


def create_session(
    session: Session,
    settings: Settings,
    *,
    user: ApplicationUser,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str, UserSession]:
    session_token = generate_opaque_token()
    refresh_token = generate_opaque_token()
    now = utc_now()
    row = UserSession(
        user_id=user.id,
        session_token_hash=_hash_token(session_token, settings),
        refresh_token_hash=_hash_token(refresh_token, settings),
        refresh_family_id=generate_opaque_token()[:36],
        refresh_generation=0,
        user_agent_hash=_audit_hash(user_agent, settings),
        ip_hash=_audit_hash(ip, settings),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(minutes=settings.auth_session_ttl_minutes),
        refresh_expires_at=now + timedelta(days=settings.auth_refresh_ttl_days),
    )
    session.add(row)
    return session_token, refresh_token, row


def _hash_registration_password(
    session: Session,
    settings: Settings,
    *,
    password: str,
    email_normalized: str,
) -> PasswordHashResult:
    try:
        return hash_password(
            password,
            pepper=settings.auth_password_pepper_current,
            pepper_version=settings.auth_password_pepper_version,
        )
    except PasswordPolicyError:
        audit(
            session,
            settings,
            event_type="user.register_failed",
            result="weak_password",
            subject=email_normalized,
        )
        session.commit()
        raise


def _ensure_identity_available(
    session: Session,
    settings: Settings,
    *,
    email_normalized: str,
    username_normalized: str,
) -> None:
    existing = session.scalar(
        select(ApplicationUser).where(
            (ApplicationUser.email_normalized == email_normalized)
            | (ApplicationUser.username_normalized == username_normalized)
        )
    )
    if existing is None:
        return
    audit(
        session,
        settings,
        event_type="user.register_failed",
        result="duplicate",
        subject=email_normalized,
    )
    session.commit()
    raise DuplicateIdentityError("identity already exists")


def _build_product_user(
    *,
    email: str,
    email_normalized: str,
    username: str,
    username_normalized: str,
    password_hash: PasswordHashResult,
    display_name: str | None,
) -> ApplicationUser:
    return ApplicationUser(
        email=email,
        email_normalized=email_normalized,
        username=username,
        username_normalized=username_normalized,
        identity_source=IdentitySource.product.value,
        credential=UserCredential(
            password_hash=password_hash.encoded_hash,
            password_hash_algorithm="argon2id",
            password_hash_params=password_hash.params,
            pepper_version=password_hash.pepper_version,
        ),
        consumer_profile=ConsumerProfile(display_name=display_name or username),
        onboarding_preferences=OnboardingPreferences(),
    )


def _add_email_verification_token(
    session: Session,
    settings: Settings,
    *,
    user: ApplicationUser,
    email: str,
    email_normalized: str,
    ip: str | None,
) -> str:
    verification_token = generate_opaque_token()
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            email=email,
            email_normalized=email_normalized,
            token_hash=_hash_token(verification_token, settings),
            expires_at=utc_now() + timedelta(hours=settings.auth_email_verification_ttl_hours),
            request_ip_hash=_audit_hash(ip, settings),
        )
    )
    return verification_token


def register_user(
    session: Session,
    settings: Settings,
    *,
    email: str,
    username: str,
    password: str,
    display_name: str | None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[ApplicationUser, str, str, str]:
    email_normalized = normalize_email(email)
    username_normalized = normalize_username(username)
    password_hash = _hash_registration_password(
        session,
        settings,
        password=password,
        email_normalized=email_normalized,
    )
    _ensure_identity_available(
        session,
        settings,
        email_normalized=email_normalized,
        username_normalized=username_normalized,
    )

    user = _build_product_user(
        email=email,
        email_normalized=email_normalized,
        username=username,
        username_normalized=username_normalized,
        password_hash=password_hash,
        display_name=display_name,
    )
    session.add(user)
    session.flush()
    verification_token = _add_email_verification_token(
        session,
        settings,
        user=user,
        email=email,
        email_normalized=email_normalized,
        ip=ip,
    )
    session_token, refresh_token, _ = create_session(
        session, settings, user=user, ip=ip, user_agent=user_agent
    )
    audit(
        session,
        settings,
        event_type="user.registered",
        result="success",
        user_id=user.id,
        subject=email_normalized,
        ip=ip,
        user_agent=user_agent,
    )
    session.commit()
    session.refresh(user)
    _send_email(
        settings,
        recipient=email,
        subject="Verify your email address",
        body=(
            f"Please verify your email address by visiting the following link:\n"
            f"https://{settings.web_host}/verify-email?token={verification_token}"
        ),
    )
    return user, session_token, refresh_token, verification_token


def authenticate_user(
    session: Session,
    settings: Settings,
    *,
    email_or_username: str,
    password: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[ApplicationUser, str, str]:
    subject = email_or_username.strip().lower()
    user = session.scalar(
        select(ApplicationUser).where(
            (
                (ApplicationUser.email_normalized == subject)
                | (ApplicationUser.username_normalized == subject)
            )
            & (ApplicationUser.identity_source == IdentitySource.product.value)
        )
    )
    if user is None or user.credential is None or user.status != "active":
        _dummy_verify_password(settings, password)
        audit(session, settings, event_type="user.login_failed", result="invalid", subject=subject)
        session.commit()
        raise AuthError("invalid credentials")
    valid = verify_password(
        password, user.credential.password_hash, pepper=settings.auth_password_pepper_current
    )
    if not valid and settings.auth_password_pepper_previous:
        valid = verify_password(
            password, user.credential.password_hash, pepper=settings.auth_password_pepper_previous
        )
        if valid:
            new_hash = hash_password(
                password,
                pepper=settings.auth_password_pepper_current,
                pepper_version=settings.auth_password_pepper_version,
            )
            user.credential.password_hash = new_hash.encoded_hash
            user.credential.password_hash_params = new_hash.params
            user.credential.pepper_version = new_hash.pepper_version
    if not valid:
        audit(session, settings, event_type="user.login_failed", result="invalid", subject=subject)
        session.commit()
        raise AuthError("invalid credentials")
    session_token, refresh_token, _ = create_session(
        session, settings, user=user, ip=ip, user_agent=user_agent
    )
    audit(
        session,
        settings,
        event_type="user.login_succeeded",
        result="success",
        user_id=user.id,
        subject=subject,
        ip=ip,
        user_agent=user_agent,
    )
    session.commit()
    session.refresh(user)
    return user, session_token, refresh_token


def get_user_by_session_token(
    session: Session, settings: Settings, token: str | None
) -> ApplicationUser | None:
    if not token:
        return None
    now = utc_now()
    row = session.scalar(
        select(UserSession).where(
            (UserSession.session_token_hash == _hash_token(token, settings))
            & (UserSession.revoked_at.is_(None))
        )
    )
    if row is None or _is_expired(row.expires_at):
        return None
    user = _active_session_user(session, row, now)
    if user is None:
        return None
    row.last_seen_at = now
    session.add(row)
    session.commit()
    return user


def _active_session_user(
    session: Session, row: UserSession, now: datetime
) -> ApplicationUser | None:
    user = row.user
    if user.status == "active":
        return user
    row.revoked_at = row.revoked_at or now
    row.revoke_reason = row.revoke_reason or "account_inactive"
    session.add(row)
    session.commit()
    return None


def refresh_session(
    session: Session, settings: Settings, refresh_token: str | None
) -> tuple[ApplicationUser, str, str]:
    if not refresh_token:
        raise AuthError("missing refresh token")
    token_hash = _hash_token(refresh_token, settings)
    row = session.scalar(select(UserSession).where(UserSession.refresh_token_hash == token_hash))
    now = utc_now()
    if row is None:
        raise AuthError("invalid refresh token")
    if row.revoked_at is not None or _is_expired(row.refresh_expires_at):
        row.revoked_at = row.revoked_at or now
        row.revoke_reason = row.revoke_reason or "refresh_expired"
        session.add(row)
        session.commit()
        raise AuthError("invalid refresh token")
    user = _active_session_user(session, row, now)
    if user is None:
        raise AuthError("invalid refresh token")

    new_session_token = generate_opaque_token()
    new_refresh_token = generate_opaque_token()
    row.session_token_hash = _hash_token(new_session_token, settings)
    row.refresh_token_hash = _hash_token(new_refresh_token, settings)
    row.refresh_generation += 1
    row.last_seen_at = now
    row.expires_at = now + timedelta(minutes=settings.auth_session_ttl_minutes)
    session.add(row)
    audit(
        session,
        settings,
        event_type="user.session_refreshed",
        result="success",
        user_id=row.user_id,
    )
    session.commit()
    session.refresh(row)
    return user, new_session_token, new_refresh_token


def revoke_session(
    session: Session, settings: Settings, session_token: str | None, refresh_token: str | None
) -> None:
    hashes = [_hash_token(token, settings) for token in (session_token, refresh_token) if token]
    if not hashes:
        return
    rows = session.scalars(
        select(UserSession).where(
            (UserSession.session_token_hash.in_(hashes))
            | (UserSession.refresh_token_hash.in_(hashes))
        )
    ).all()
    now = utc_now()
    for row in rows:
        row.revoked_at = now
        row.revoke_reason = "logout"
        session.add(row)
    session.commit()


def confirm_email_verification(session: Session, settings: Settings, token: str) -> ApplicationUser:
    row = session.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == _hash_token(token, settings)
        )
    )
    now = utc_now()
    if (
        row is None
        or row.consumed_at is not None
        or row.expires_at is not None
        and _is_expired(row.expires_at)
    ):
        raise AuthError("invalid verification token")
    user = session.get(ApplicationUser, row.user_id)
    if user is None:
        raise AuthError("invalid verification token")
    user.email_verified_at = now
    row.consumed_at = now
    session.add_all([user, row])
    audit(session, settings, event_type="user.email_verified", result="success", user_id=user.id)
    session.commit()
    session.refresh(user)
    return user


def request_email_verification(session: Session, settings: Settings, user: ApplicationUser) -> str:
    token = generate_opaque_token()
    now = utc_now()
    for existing in session.scalars(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.consumed_at.is_(None),
        )
    ):
        existing.consumed_at = now
        session.add(existing)
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            email=user.email or "",
            email_normalized=user.email_normalized or "",
            token_hash=_hash_token(token, settings),
            expires_at=now + timedelta(hours=settings.auth_email_verification_ttl_hours),
        )
    )
    session.commit()
    _send_email(
        settings,
        recipient=user.email or "",
        subject="Verify your email address",
        body=(
            f"Please verify your email address by visiting the following link:\n"
            f"https://{settings.web_host}/verify-email?token={token}"
        ),
    )
    return token


def request_password_reset(session: Session, settings: Settings, email: str) -> str | None:
    email_normalized = normalize_email(email)
    user = session.scalar(
        select(ApplicationUser).where(
            (ApplicationUser.email_normalized == email_normalized)
            & (ApplicationUser.identity_source == IdentitySource.product.value)
        )
    )
    token: str | None = None
    if user is not None:
        token = generate_opaque_token()
        now = utc_now()
        for existing in session.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.consumed_at.is_(None),
            )
        ):
            existing.consumed_at = now
            session.add(existing)
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=_hash_token(token, settings),
                expires_at=now + timedelta(minutes=settings.auth_password_reset_ttl_minutes),
            )
        )
    audit(
        session,
        settings,
        event_type="user.password_reset_requested",
        result="generic",
        subject=email_normalized,
    )
    session.commit()
    if token is not None and user is not None:
        _send_email(
            settings,
            recipient=email,
            subject="Reset your password",
            body=(
                f"Please reset your password by visiting the following link:\n"
                f"https://{settings.web_host}/reset-password?token={token}"
            ),
        )
    return token


def confirm_password_reset(
    session: Session, settings: Settings, *, token: str, new_password: str
) -> None:
    row = session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_token(token, settings)
        )
    )
    now = utc_now()
    if (
        row is None
        or row.consumed_at is not None
        or row.expires_at is not None
        and _is_expired(row.expires_at)
    ):
        raise AuthError("invalid reset token")
    user = session.get(ApplicationUser, row.user_id)
    if user is None or user.credential is None:
        raise AuthError("invalid reset token")
    new_hash = hash_password(
        new_password,
        pepper=settings.auth_password_pepper_current,
        pepper_version=settings.auth_password_pepper_version,
    )
    user.credential.password_hash = new_hash.encoded_hash
    user.credential.password_hash_params = new_hash.params
    user.credential.pepper_version = new_hash.pepper_version
    user.credential.password_changed_at = now
    row.consumed_at = now
    for active_session in session.scalars(
        select(UserSession).where(
            (UserSession.user_id == user.id) & (UserSession.revoked_at.is_(None))
        )
    ):
        active_session.revoked_at = now
        active_session.revoke_reason = "password_reset"
        session.add(active_session)
    session.add_all([user, row])
    audit(
        session,
        settings,
        event_type="user.password_reset_confirmed",
        result="success",
        user_id=user.id,
    )
    session.commit()
