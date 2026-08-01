import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

_APP_ENV = os.getenv("ERP_ENV", "development")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Configuración desde variables de entorno (valores actuales como fallback)."""

    app_env: str = _APP_ENV
    secret_key: str = os.getenv(
        "ERP_SECRET_KEY",
        "erp-dev-secret-change-in-production",
    )
    secretadmin_password: str = os.getenv(
        "ERP_SECRETADMIN_PASSWORD",
        "203211",
    )
    session_max_age: int = int(os.getenv("ERP_SESSION_MAX_AGE", str(60 * 60 * 24 * 7)))
    admin_session_max_age: int = int(os.getenv("ERP_ADMIN_SESSION_MAX_AGE", "3600"))
    per_page: int = int(os.getenv("ERP_PER_PAGE", "20"))
    cookie_secure: bool = _env_bool(
        "ERP_COOKIE_SECURE",
        _APP_ENV.lower() == "production",
    )

    database_url: str = os.getenv("DATABASE_URL", "")
    database_pool_size: int = int(os.getenv("DB_POOL_SIZE", "20"))
    database_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "40"))
    database_pool_recycle: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    encryption_key: str = os.getenv("ERP_ENCRYPTION_KEY", "")

    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")
    smtp_use_tls: bool = _env_bool("SMTP_USE_TLS", True)
    smtp_enabled: bool = _env_bool("SMTP_ENABLED", False)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

settings = Settings()
