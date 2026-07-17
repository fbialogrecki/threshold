import hmac
import secrets
from hashlib import sha256


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def generate_opaque_token() -> str:
    return new_opaque_token()


def hash_token(token: str, *, key: str) -> str:
    return hmac.new(key.encode("utf-8"), token.encode("utf-8"), sha256).hexdigest()


def keyed_hash(value: str, key: str) -> str:
    return hash_token(value, key=key)


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)


def hash_subject(value: str | None, *, key: str) -> str | None:
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    return hash_token(normalized, key=key)


def stable_hash(value: str | None, key: str) -> str | None:
    return hash_subject(value, key=key)
