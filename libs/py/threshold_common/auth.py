from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError


@dataclass(frozen=True)
class Principal:
    subject: str
    email: str | None = None
    username: str | None = None
    claims: dict[str, Any] | None = None


class AuthError(ValueError):
    """Raised when authentication material is missing or invalid."""


class AuthConfigurationError(RuntimeError):
    """Raised when auth validation cannot run safely."""


def require_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise AuthError("empty bearer token")
    return token


class JwtVerifier:
    def __init__(
        self,
        *,
        issuer: str | None,
        jwks_url: str | None,
        audience: str | None = None,
        algorithms: tuple[str, ...] = ("RS256",),
    ) -> None:
        self.issuer = issuer
        self.jwks_url = jwks_url
        self.audience = audience
        self.algorithms = algorithms
        self._jwks_client: PyJWKClient | None = None

    def _client(self) -> PyJWKClient:
        if not self.jwks_url:
            raise AuthConfigurationError("JWKS URL is not configured")
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(self.jwks_url)
        return self._jwks_client

    def verify(self, token: str) -> Principal:
        if not self.issuer:
            raise AuthConfigurationError("OIDC issuer is not configured")

        try:
            signing_key = self._client().get_signing_key_from_jwt(token)
            options: Any = {"verify_aud": bool(self.audience)}
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self.algorithms),
                issuer=self.issuer,
                audience=self.audience,
                options=options,
            )
        except (InvalidTokenError, PyJWKClientError) as exc:
            raise AuthError("invalid bearer token") from exc

        if not isinstance(claims, dict):
            raise AuthError("invalid token claims")

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthError("token subject is missing")

        email = claims.get("email")
        username = claims.get("preferred_username") or claims.get("username")
        return Principal(
            subject=subject,
            email=email if isinstance(email, str) else None,
            username=username if isinstance(username, str) else None,
            claims=claims,
        )
