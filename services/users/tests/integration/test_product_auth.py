from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from users.auth.tokens import keyed_hash
from users.domain.models import (
    ApplicationUser,
    AuthAuditLog,
    EmailVerificationToken,
    PasswordResetToken,
    UserCredential,
    UserSession,
)
from users.main import app
from users.main_dependencies import settings


def test_register_creates_product_user_credential_profile_and_restricted_session(
    session: Session,
) -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/auth/register",
        json={
            "email": "Person@Example.Test",
            "username": "New_User",
            "password": "StrongPass123!",
            "display_name": "New User",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "Person@Example.Test"
    assert body["user"]["email_normalized"] == "person@example.test"
    assert body["user"]["username_normalized"] == "new_user"
    assert body["user"]["email_verified"] is False
    assert body["consumer_profile"]["display_name"] == "New User"
    assert response.cookies.get("threshold_session")
    assert response.cookies.get("threshold_refresh")

    user = session.scalar(
        select(ApplicationUser).where(ApplicationUser.email_normalized == "person@example.test")
    )
    assert user is not None
    assert user.identity_source == "product"
    assert user.authentik_subject is None
    assert user.consumer_profile is not None
    assert user.onboarding_preferences is not None

    credential = session.scalar(select(UserCredential).where(UserCredential.user_id == user.id))
    assert credential is not None
    assert credential.password_hash_algorithm == "argon2id"
    assert credential.password_hash.startswith("$argon2id$")
    assert "StrongPass123!" not in credential.password_hash
    assert credential.pepper_version == 1

    verification_token = session.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    assert verification_token is not None
    assert verification_token.token_hash
    assert verification_token.token_hash != body["dev_email_verification_token"]

    user_session = session.scalar(select(UserSession).where(UserSession.user_id == user.id))
    assert user_session is not None
    assert user_session.session_token_hash
    assert user_session.refresh_token_hash

    audit_log = session.scalar(
        select(AuthAuditLog).where(
            AuthAuditLog.user_id == user.id,
            AuthAuditLog.event_type == "user.registered",
            AuthAuditLog.result == "success",
        )
    )
    assert audit_log is not None


def test_register_rejects_password_without_required_complexity(session: Session) -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/auth/register",
        json={
            "email": "weak@example.test",
            "username": "weakuser",
            "password": "longbutweakpassword",
        },
    )

    assert response.status_code == 422
    assert (
        session.scalar(
            select(ApplicationUser).where(ApplicationUser.email_normalized == "weak@example.test")
        )
        is None
    )
    audit_log = session.scalar(
        select(AuthAuditLog).where(
            AuthAuditLog.event_type == "user.register_failed",
            AuthAuditLog.result == "weak_password",
        )
    )
    assert audit_log is not None


def test_register_validates_password_before_duplicate_identity(session: Session) -> None:
    client = TestClient(app)
    assert (
        client.post(
            "/v1/auth/register",
            json={
                "email": "oracle@example.test",
                "username": "oracle",
                "password": "StrongPass123!",
            },
        ).status_code
        == 201
    )

    duplicate_weak = client.post(
        "/v1/auth/register",
        json={
            "email": "oracle@example.test",
            "username": "oracle",
            "password": "longbutweakpassword",
        },
    )

    assert duplicate_weak.status_code == 422


def test_register_rejects_duplicate_identity_with_audit(session: Session) -> None:
    client = TestClient(app)
    assert (
        client.post(
            "/v1/auth/register",
            json={
                "email": "duplicate@example.test",
                "username": "duplicate",
                "password": "StrongPass123!",
            },
        ).status_code
        == 201
    )

    duplicate = client.post(
        "/v1/auth/register",
        json={
            "email": "DUPLICATE@example.test",
            "username": "otherduplicate",
            "password": "StrongPass123!",
        },
    )

    assert duplicate.status_code == 409
    audit_log = session.scalar(
        select(AuthAuditLog).where(
            AuthAuditLog.event_type == "user.register_failed",
            AuthAuditLog.result == "duplicate",
        )
    )
    assert audit_log is not None


def test_login_me_refresh_and_logout_use_opaque_hashed_cookies(session: Session) -> None:
    client = TestClient(app)
    client.post(
        "/v1/auth/register",
        json={
            "email": "login@example.test",
            "username": "loginuser",
            "password": "StrongPass123!",
        },
    )
    client.cookies.clear()

    login = client.post(
        "/v1/auth/login",
        json={"email_or_username": "LOGINUSER", "password": "StrongPass123!"},
    )

    assert login.status_code == 200
    session_cookie = login.cookies.get("threshold_session")
    refresh_cookie = login.cookies.get("threshold_refresh")
    assert session_cookie
    assert refresh_cookie
    assert (
        session.scalar(select(UserSession).where(UserSession.session_token_hash == session_cookie))
        is None
    )
    assert (
        session.scalar(select(UserSession).where(UserSession.refresh_token_hash == refresh_cookie))
        is None
    )

    me = client.get("/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username_normalized"] == "loginuser"

    first_refresh_row = session.scalar(
        select(UserSession).where(
            UserSession.refresh_token_hash
            == keyed_hash(refresh_cookie, settings.auth_session_token_hmac_key)
        )
    )
    assert first_refresh_row is not None
    first_generation = first_refresh_row.refresh_generation
    refresh = client.post("/v1/auth/refresh")
    assert refresh.status_code == 200
    session.refresh(first_refresh_row)
    assert first_refresh_row.refresh_generation == first_generation + 1
    assert refresh.cookies.get("threshold_refresh") != refresh_cookie

    logout = client.post("/v1/auth/logout")
    assert logout.status_code == 204
    assert client.get("/v1/auth/me").status_code == 401


def test_locked_account_session_and_refresh_are_rejected_and_cleared(
    session: Session,
) -> None:
    current_client = TestClient(app)
    current_register = current_client.post(
        "/v1/auth/register",
        json={
            "email": "locked-current@example.test",
            "username": "lockedcurrent",
            "password": "StrongPass123!",
        },
    )
    current_user = session.get(ApplicationUser, current_register.json()["user"]["id"])
    assert current_user is not None
    current_user.status = "locked"
    session.commit()

    current = current_client.get("/v1/me/follows")
    session.expire_all()
    current_session = session.scalar(
        select(UserSession).where(UserSession.user_id == current_user.id)
    )

    assert current.status_code == 401
    assert current.json() == {"detail": "not authenticated"}
    assert current_client.cookies.get("threshold_session") is None
    assert current_client.cookies.get("threshold_refresh") is None
    assert current_session is not None
    assert current_session.revoked_at is not None
    assert current_session.revoke_reason == "account_inactive"

    refresh_client = TestClient(app)
    refresh_register = refresh_client.post(
        "/v1/auth/register",
        json={
            "email": "locked-refresh@example.test",
            "username": "lockedrefresh",
            "password": "StrongPass123!",
        },
    )
    refresh_user = session.get(ApplicationUser, refresh_register.json()["user"]["id"])
    assert refresh_user is not None
    refresh_user.status = "locked"
    session.commit()

    refreshed = refresh_client.post("/v1/auth/refresh")
    session.expire_all()
    refresh_session_row = session.scalar(
        select(UserSession).where(UserSession.user_id == refresh_user.id)
    )

    assert refreshed.status_code == 401
    assert refreshed.json() == {"detail": "invalid refresh token"}
    assert refresh_client.cookies.get("threshold_session") is None
    assert refresh_client.cookies.get("threshold_refresh") is None
    assert refresh_session_row is not None
    assert refresh_session_row.revoked_at is not None
    assert refresh_session_row.revoke_reason == "account_inactive"


def test_email_verify_and_password_reset_tokens_are_single_use_and_hashed(session: Session) -> None:
    client = TestClient(app)
    register = client.post(
        "/v1/auth/register",
        json={
            "email": "verify@example.test",
            "username": "verifyuser",
            "password": "StrongPass123!",
        },
    )
    verify_token = register.json()["dev_email_verification_token"]
    new_verify_request = client.post("/v1/auth/email/verify/request")
    assert new_verify_request.status_code == 200
    new_verify_token = new_verify_request.json()["dev_email_verification_token"]

    assert (
        client.post("/v1/auth/email/verify/confirm", json={"token": verify_token}).status_code
        == 400
    )
    verify = client.post("/v1/auth/email/verify/confirm", json={"token": new_verify_token})
    assert verify.status_code == 200
    assert verify.json()["user"]["email_verified"] is True
    assert (
        client.post("/v1/auth/email/verify/confirm", json={"token": verify_token}).status_code
        == 400
    )

    reset_request = client.post(
        "/v1/auth/password/reset/request",
        json={"email": "verify@example.test"},
    )
    assert reset_request.status_code == 200
    reset_token = reset_request.json()["dev_password_reset_token"]
    replacement_reset_request = client.post(
        "/v1/auth/password/reset/request",
        json={"email": "verify@example.test"},
    )
    assert replacement_reset_request.status_code == 200
    replacement_reset_token = replacement_reset_request.json()["dev_password_reset_token"]
    reset_row = session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.consumed_at.is_(None))
    )
    assert reset_row is not None
    assert reset_row.token_hash != replacement_reset_token
    assert (
        client.post(
            "/v1/auth/password/reset/confirm",
            json={"token": reset_token, "new_password": "AnotherStrong123!"},
        ).status_code
        == 400
    )

    reset = client.post(
        "/v1/auth/password/reset/confirm",
        json={"token": replacement_reset_token, "new_password": "NewStrong123!"},
    )
    assert reset.status_code == 200
    assert (
        client.post(
            "/v1/auth/login",
            json={"email_or_username": "verify@example.test", "password": "NewStrong123!"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/auth/password/reset/confirm",
            json={"token": replacement_reset_token, "new_password": "AnotherStrong123!"},
        ).status_code
        == 400
    )


def test_auth_audit_logs_hash_subjects_without_raw_email(session: Session) -> None:
    client = TestClient(app)
    client.post(
        "/v1/auth/register",
        json={
            "email": "audit@example.test",
            "username": "audituser",
            "password": "StrongPass123!",
        },
    )

    logs = session.scalars(select(AuthAuditLog)).all()
    assert logs
    serialized = " ".join(str(log.metadata_json) + " " + str(log.subject_hash) for log in logs)
    assert "audit@example.test" not in serialized
