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

    # Telegram Bot (notificaciones externas)
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    enable_telegram: bool = _env_bool(
        "ENABLE_TELEGRAM",
        _env_bool("TELEGRAM_ENABLED", False),
    )

    # Cookies/sesión legacy (texto plano / token "authenticated"). Off por defecto.
    allow_legacy_session: bool = _env_bool("ERP_ALLOW_LEGACY_SESSION", False)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate_security_settings(self) -> None:
        """En producción, aborta si secrets por defecto siguen activos."""
        if not self.is_production:
            return
        weak: list[str] = []
        if self.secret_key in {"", "erp-dev-secret-change-in-production"}:
            weak.append("ERP_SECRET_KEY")
        if self.secretadmin_password in {"", "203211"}:
            weak.append("ERP_SECRETADMIN_PASSWORD")
        if weak:
            raise RuntimeError(
                "Configuración insegura en producción. Cambie: " + ", ".join(weak)
            )


settings = Settings()
