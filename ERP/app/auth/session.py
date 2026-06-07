from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config.settings import settings

_user_serializer = URLSafeTimedSerializer(
    settings.secret_key,
    salt="erp-user-session",
)
_admin_serializer = URLSafeTimedSerializer(
    settings.secret_key,
    salt="erp-admin-session",
)

LEGACY_ADMIN_TOKEN = "authenticated"


def sign_user_session(username: str) -> str:
    return _user_serializer.dumps({"username": username})


def resolve_user_session(cookie_value: str | None) -> str | None:
    if not cookie_value:
        return None
    try:
        data = _user_serializer.loads(
            cookie_value,
            max_age=settings.session_max_age,
        )
        username = data.get("username")
        return username if username else None
    except (BadSignature, SignatureExpired):
        pass
    # Compatibilidad: cookie antigua con username en texto plano
    if (
        cookie_value
        and cookie_value != LEGACY_ADMIN_TOKEN
        and len(cookie_value) <= 150
        and " " not in cookie_value
        and cookie_value.count(".") < 2
    ):
        return cookie_value
    return None


def sign_admin_session() -> str:
    return _admin_serializer.dumps({"admin": True})


def is_admin_session_valid(cookie_value: str | None) -> bool:
    if not cookie_value:
        return False
    if cookie_value == LEGACY_ADMIN_TOKEN:
        return True
    try:
        data = _admin_serializer.loads(
            cookie_value,
            max_age=settings.admin_session_max_age,
        )
        return bool(data.get("admin"))
    except (BadSignature, SignatureExpired):
        return False


def cookie_options() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "max_age": settings.session_max_age,
    }


def admin_cookie_options() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "max_age": settings.admin_session_max_age,
    }
