import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

_APP_ENV = os.getenv("ERP_ENV", "development")

_DEV_DATABASE_URL = (
    "mysql+pymysql://erp_user:erppassword@127.0.0.1:3307/erp?charset=utf8mb4"
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_database_url() -> str:
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    if _APP_ENV.lower() == "production":
        raise RuntimeError(
            "DATABASE_URL es obligatorio cuando ERP_ENV=production"
        )

    return _DEV_DATABASE_URL


class Settings:
    """Configuración desde variables de entorno."""

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

    database_url: str = _resolve_database_url()
    database_pool_size: int = int(os.getenv("DB_POOL_SIZE", "20"))
    database_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "40"))
    database_pool_recycle: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        return not self.is_production

    @property
    def uses_portable_mysql(self) -> bool:
        """MariaDB portable local (solo desarrollo, puerto 3307)."""
        parsed = urlparse(self.database_url.replace("+pymysql", "", 1))
        return parsed.hostname in {"127.0.0.1", "localhost"} and parsed.port == 3307


settings = Settings()
