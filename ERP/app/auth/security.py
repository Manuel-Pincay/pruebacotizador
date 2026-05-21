import hashlib


def hash_password(password: str):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()


def verify_password(
    plain_password,
    hashed_password
):

    return hashlib.sha256(
        plain_password.encode()
    ).hexdigest() == hashed_password