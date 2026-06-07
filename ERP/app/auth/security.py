import hashlib

import bcrypt


def _is_legacy_sha256(hashed_password: str) -> bool:
    return (
        len(hashed_password) == 64
        and all(c in "0123456789abcdef" for c in hashed_password.lower())
    )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if _is_legacy_sha256(hashed_password):
        return (
            hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password
        )
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False
