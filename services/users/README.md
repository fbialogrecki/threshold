# users

Threshold application users service.

## Scope

Current vertical slice:

- application users and consumer profiles,
- transitional Authentik subject mapping for internal/admin SSO flows,
- product-auth target module for public custom register/login,
- onboarding preferences,
- Page and PageMembership schema baseline.

Authentik is not the product-auth source for public Threshold users. Product login/register belongs in this service as the `users` auth module unless it is later extracted into a dedicated `auth` service.

## API

- `GET /healthz`
- `GET /readyz`
- `POST /internal/v1/current-profile`
- `PUT /internal/v1/users/{user_id}/onboarding-preferences`

Planned public product-auth API:

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/logout`
- `POST /v1/auth/refresh`
- `GET /v1/auth/me`
- `POST /v1/auth/email/verify/request`
- `POST /v1/auth/email/verify/confirm`
- `POST /v1/auth/password/reset/request`
- `POST /v1/auth/password/reset/confirm`

The internal API is intended for service-to-service calls from `auth-gateway`; it is not a public browser-facing API. The planned `/v1/auth/*` API is the product-auth browser path, normally reached through a thin Next.js BFF for same-origin cookie ergonomics.

## Configuration

Environment variables use the `THRESHOLD_` prefix.

- `THRESHOLD_DATABASE_URL` — SQLAlchemy database URL. Local tests use SQLite; cluster runtime uses ESO/OpenBao materialized DB credentials.
- `THRESHOLD_AUTH_PASSWORD_PEPPER_CURRENT` — current product-auth password pepper from OpenBao/ESO.
- `THRESHOLD_AUTH_PASSWORD_PEPPER_VERSION` — current pepper version.
- `THRESHOLD_AUTH_SESSION_TOKEN_HMAC_KEY` — key for hashing/verifying opaque session tokens.
- `THRESHOLD_AUTH_AUDIT_HASH_KEY` — key for hashing audit identifiers such as email/IP/user-agent.
- `THRESHOLD_SMTP_HOST` / `THRESHOLD_SMTP_PORT` — SMTP endpoint. Cluster defaults target Resend SMTP at `smtp.resend.com:587`.
- `THRESHOLD_SMTP_SECURITY` — explicit transport mode: `starttls`, `implicit_tls`, or `plaintext`. Plaintext delivery is restricted to local/test environments; cluster delivery uses STARTTLS without downgrade.
- `THRESHOLD_SMTP_TIMEOUT_SECONDS` — bounded connection/operation timeout, greater than zero and at most 30 seconds.
- `THRESHOLD_SMTP_CA_FILE` — optional path to a private CA bundle. When unset, the operating system trust store is used.
- `THRESHOLD_SMTP_ENABLED` — enable real email delivery. Keep this in OpenBao with the email credentials so missing credentials do not accidentally enable delivery.
- `THRESHOLD_SMTP_USERNAME` — Resend SMTP username, normally `resend`.
- `THRESHOLD_SMTP_PASSWORD` — Resend API key used as the SMTP password.
- `THRESHOLD_SMTP_FROM` — verified sender address, for example `Threshold <no-reply@example.com>`.
- `THRESHOLD_WEB_HOST` — public web host used in email verification and password reset links, without scheme.

Cluster email runtime reads `THRESHOLD_SMTP_ENABLED`, `THRESHOLD_SMTP_USERNAME`, `THRESHOLD_SMTP_PASSWORD`, `THRESHOLD_SMTP_FROM`, and `THRESHOLD_WEB_HOST` from OpenBao path `threshold/users/email` via `ExternalSecret/users-email`.

## Local checks

```bash
go-task service:test SERVICE=users
go-task py:lint
go-task py:typecheck
go-task py:test
```
