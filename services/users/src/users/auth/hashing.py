import re
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 1024

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


@dataclass(frozen=True)
class PasswordHashResult:
    encoded_hash: str
    params: dict[str, int | str]
    pepper_version: int


class PasswordPolicyError(ValueError):
    pass


def validate_password_policy(password: str) -> None:
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append("at least 12 characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append("too long")
    if not re.search(r"[a-z]", password):
        errors.append("lowercase letter")
    if not re.search(r"[A-Z]", password):
        errors.append("uppercase letter")
    if not re.search(r"\d", password):
        errors.append("digit")
    if not re.search(r"[^A-Za-z0-9\s]", password):
        errors.append("special character")
    if errors:
        raise PasswordPolicyError("Password must include " + ", ".join(errors))


def _peppered_password(password: str, pepper: str) -> str:
    import hashlib
    import hmac

    return hmac.new(pepper.encode("utf-8"), password.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_password(password: str, *, pepper: str, pepper_version: int) -> PasswordHashResult:
    validate_password_policy(password)
    encoded_hash = _password_hasher.hash(_peppered_password(password, pepper))
    return PasswordHashResult(
        encoded_hash=encoded_hash,
        pepper_version=pepper_version,
        params={
            "algorithm": "argon2id",
            "memory_cost": 65536,
            "time_cost": 3,
            "parallelism": 2,
            "hash_len": 32,
            "salt_len": 16,
        },
    )


def verify_password(password: str, encoded_hash: str, *, pepper: str) -> bool:
    try:
        return _password_hasher.verify(encoded_hash, _peppered_password(password, pepper))
    except VerifyMismatchError:
        return False
