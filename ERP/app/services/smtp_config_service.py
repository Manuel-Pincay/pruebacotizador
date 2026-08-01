"""Configuración SMTP: base de datos (UI) con respaldo en .env."""
from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import settings
from app.utils.encryption import decrypt_text, encrypt_text


@dataclass
class SmtpSettings:
    enabled: bool
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    use_tls: bool
    source: str  # db | env


def _from_env() -> SmtpSettings | None:
    if not settings.smtp_enabled or not settings.smtp_host or not settings.smtp_from:
        return None
    return SmtpSettings(
        enabled=True,
        host=settings.smtp_host.strip(),
        port=int(settings.smtp_port or 587),
        user=(settings.smtp_user or "").strip(),
        password=settings.smtp_password or "",
        from_addr=settings.smtp_from.strip(),
        use_tls=bool(settings.smtp_use_tls),
        source="env",
    )


def _from_db(config) -> SmtpSettings | None:
    if not config or not getattr(config, "smtp_enabled", False):
        return None
    host = (getattr(config, "smtp_host", None) or "").strip()
    from_addr = (getattr(config, "smtp_from", None) or "").strip()
    if not host or not from_addr:
        return None
    password = ""
    encrypted = getattr(config, "smtp_password_encrypted", None)
    if encrypted:
        try:
            password = decrypt_text(encrypted)
        except Exception:
            password = ""
    return SmtpSettings(
        enabled=True,
        host=host,
        port=int(getattr(config, "smtp_port", None) or 587),
        user=(getattr(config, "smtp_user", None) or "").strip(),
        password=password,
        from_addr=from_addr,
        use_tls=bool(getattr(config, "smtp_use_tls", True)),
        source="db",
    )


def resolve_smtp_settings(config=None) -> SmtpSettings | None:
    """Prioridad: configuración guardada en ERP; si no, variables .env."""
    db_settings = _from_db(config)
    if db_settings:
        return db_settings
    return _from_env()


def smtp_configured(config=None) -> bool:
    return resolve_smtp_settings(config) is not None


def smtp_password_configured(config=None) -> bool:
    if config and getattr(config, "smtp_password_encrypted", None):
        return True
    return bool(settings.smtp_password)


def save_smtp_password(config, plain_password: str | None) -> None:
    if plain_password is None:
        return
    pwd = (plain_password or "").strip()
    if pwd:
        config.smtp_password_encrypted = encrypt_text(pwd)
    # vacío = mantener la actual (no borrar)


def resolve_smtp_password(plain_password: str | None, config=None) -> str:
    pwd = (plain_password or "").strip()
    if pwd:
        return pwd
    if config and getattr(config, "smtp_password_encrypted", None):
        try:
            return decrypt_text(config.smtp_password_encrypted)
        except Exception:
            return ""
    return settings.smtp_password or ""


def build_smtp_settings_from_form(
    *,
    enabled: bool,
    host: str | None,
    port: int,
    user: str | None,
    from_addr: str | None,
    password_plain: str | None,
    use_tls: bool,
    existing_config=None,
) -> SmtpSettings | None:
    if not enabled:
        return None
    host_val = (host or "").strip()
    from_val = (from_addr or "").strip()
    user_val = (user or "").strip() or from_val
    if not host_val or not from_val:
        return None
    return SmtpSettings(
        enabled=True,
        host=host_val,
        port=max(1, min(int(port or 587), 65535)),
        user=user_val,
        password=resolve_smtp_password(password_plain, existing_config),
        from_addr=from_val,
        use_tls=use_tls,
        source="db",
    )
