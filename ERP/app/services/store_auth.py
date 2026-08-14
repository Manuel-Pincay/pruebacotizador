"""Sesión del portal de clientes de la tienda (independiente del ERP)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.config.settings import settings
from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.utils.text_format import format_title_words

CLIENT_COOKIE = "store_client"
CLIENT_MAX_AGE = settings.session_max_age
VERIFY_CODE_TTL_MINUTES = 20

_client_serializer = URLSafeTimedSerializer(
    settings.secret_key,
    salt="store-client-portal-v1",
)
_verify_serializer = URLSafeTimedSerializer(
    settings.secret_key,
    salt="store-client-verify-v1",
)


class PortalEmailPending(Exception):
    """Cuenta creada pero falta confirmar el código del correo."""

    def __init__(self, client_id: int, email: str, message: str = ""):
        self.client_id = client_id
        self.email = email
        super().__init__(message or "Debes confirmar tu correo.")


def sign_client_session(client_id: int) -> str:
    return _client_serializer.dumps({"cid": int(client_id)})


def sign_verify_token(client_id: int) -> str:
    return _verify_serializer.dumps({"cid": int(client_id)})


def resolve_verify_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        data = _verify_serializer.loads(token, max_age=60 * 60 * 24)
        return int(data.get("cid"))
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def resolve_client_id(cookie_value: str | None) -> int | None:
    if not cookie_value:
        return None
    try:
        data = _client_serializer.loads(cookie_value, max_age=CLIENT_MAX_AGE)
        cid = data.get("cid")
        return int(cid) if cid is not None else None
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def client_cookie_options() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "max_age": CLIENT_MAX_AGE,
        "path": "/",
    }


def get_portal_client(db: Session, cookie_value: str | None) -> Client | None:
    cid = resolve_client_id(cookie_value)
    if not cid:
        return None
    client = db.query(Client).filter(Client.id == cid).first()
    if not client or not client.portal_active or not client.password_hash:
        return None
    return client


def _new_verify_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_verify_code(client: Client) -> str:
    code = _new_verify_code()
    client.portal_verify_code = code
    client.portal_verify_expires = datetime.utcnow() + timedelta(
        minutes=VERIFY_CODE_TTL_MINUTES
    )
    client.portal_active = False
    return code


def send_portal_verify_email(db: Session, client: Client, code: str) -> None:
    from app.services.email_service import EmailDeliveryError, send_email
    from app.services.smtp_config_service import smtp_configured

    config = db.query(CompanyConfig).first()
    if not smtp_configured(config):
        raise EmailDeliveryError(
            "El correo no está configurado. Configure SMTP en "
            "Configuración de empresa → Correo SMTP."
        )

    company = (config.company_name if config else None) or "Tienda"
    name = (client.name or "").strip() or "cliente"
    subject = f"{company} — Código de verificación"
    body = (
        f"Hola {name},\n\n"
        f"Tu código para confirmar la cuenta en {company} es:\n\n"
        f"    {code}\n\n"
        f"Válido por {VERIFY_CODE_TTL_MINUTES} minutos.\n"
        "Si no creaste esta cuenta, ignora este mensaje.\n"
    )
    html = (
        f"<div style='font-family:system-ui,sans-serif;max-width:480px;margin:0 auto'>"
        f"<p>Hola {name},</p>"
        f"<p>Tu código para confirmar la cuenta en <strong>{company}</strong> es:</p>"
        f"<p style='font-size:28px;letter-spacing:6px;font-weight:700;"
        f"background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;"
        f"padding:16px 20px;text-align:center'>{code}</p>"
        f"<p style='color:#64748b;font-size:14px'>Válido por "
        f"{VERIFY_CODE_TTL_MINUTES} minutos.</p>"
        f"<p style='color:#94a3b8;font-size:12px'>Si no creaste esta cuenta, "
        f"ignora este mensaje.</p>"
        f"</div>"
    )
    send_email(
        to_addresses=[client.email],
        subject=subject,
        body_text=body,
        body_html=html,
        from_name=company,
        config=config,
    )


def register_portal_client(
    db: Session,
    *,
    name: str,
    email: str,
    phone: str,
    password: str,
    ruc_ci: str = "",
    address: str = "",
    auto_activate: bool = False,
) -> tuple[Client, str | None]:
    """
    Crea/actualiza cliente de portal.
    Retorna (client, código) — código es None si auto_activate=True.
    Por defecto la cuenta queda inactiva hasta confirmar el email.
    """
    name = format_title_words((name or "").strip())
    email = (email or "").strip().lower()
    phone = (phone or "").strip()
    password = (password or "").strip()
    ruc_ci = (ruc_ci or "").strip()
    address = format_title_words((address or "").strip())

    if len(name) < 2:
        raise ValueError("Indica tu nombre.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Indica un email válido.")
    if len(phone) < 7:
        raise ValueError("Indica un teléfono válido.")
    if len(password) < 6:
        raise ValueError("La clave debe tener al menos 6 caracteres.")

    existing_active = (
        db.query(Client)
        .filter(Client.email == email, Client.portal_active.is_(True))
        .first()
    )
    if existing_active:
        raise ValueError("Ya existe una cuenta con ese email. Inicia sesión.")

    client = None
    if ruc_ci:
        client = db.query(Client).filter(Client.ruc_ci == ruc_ci).first()
        if client and client.portal_active and client.password_hash:
            raise ValueError("Esa cédula/RUC ya tiene cuenta. Inicia sesión.")
    if not client:
        client = (
            db.query(Client)
            .filter(Client.email == email)
            .order_by(Client.id.desc())
            .first()
        )

    if client:
        client.name = name or client.name
        client.phone = phone or client.phone
        client.email = email
        if address:
            client.address = address
        if ruc_ci and not client.ruc_ci:
            client.ruc_ci = ruc_ci
        client.password_hash = hash_password(password)
        if not client.client_type:
            client.client_type = "tienda"
    else:
        client = Client(
            name=name,
            email=email,
            phone=phone,
            ruc_ci=ruc_ci or None,
            address=address or None,
            client_type="tienda",
            tipo_identificacion="CEDULA" if ruc_ci and len(ruc_ci) <= 10 else "RUC",
            password_hash=hash_password(password),
            portal_active=False,
            observations="Cuenta creada desde tienda virtual",
        )
        db.add(client)

    db.flush()

    if auto_activate:
        client.portal_active = True
        client.portal_verify_code = None
        client.portal_verify_expires = None
        return client, None

    code = issue_verify_code(client)
    return client, code


def confirm_portal_email(db: Session, *, client_id: int, code: str) -> Client:
    code = (code or "").strip()
    if len(code) < 4:
        raise ValueError("Ingresa el código de 6 dígitos.")

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client or not client.password_hash:
        raise ValueError("Cuenta no encontrada. Regístrate de nuevo.")

    if client.portal_active and not client.portal_verify_code:
        return client

    expected = (client.portal_verify_code or "").strip()
    expires = client.portal_verify_expires
    if not expected:
        raise ValueError("No hay un código pendiente. Solicita uno nuevo.")
    if expires and datetime.utcnow() > expires:
        raise ValueError("El código expiró. Solicita uno nuevo.")
    if code != expected:
        raise ValueError("Código incorrecto.")

    client.portal_active = True
    client.portal_verify_code = None
    client.portal_verify_expires = None
    db.flush()
    return client


def resend_portal_verify_code(db: Session, *, client_id: int) -> str:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client or not client.password_hash:
        raise ValueError("Cuenta no encontrada.")
    if client.portal_active and not client.portal_verify_code:
        raise ValueError("Esta cuenta ya está confirmada. Inicia sesión.")
    code = issue_verify_code(client)
    db.flush()
    send_portal_verify_email(db, client, code)
    return code


def authenticate_portal_client(
    db: Session, *, email: str, password: str
) -> Client:
    email = (email or "").strip().lower()
    password = (password or "").strip()
    if not email or not password:
        raise ValueError("Email y clave son obligatorios.")

    client = (
        db.query(Client)
        .filter(
            Client.email == email,
            Client.password_hash.isnot(None),
        )
        .order_by(Client.id.desc())
        .first()
    )
    if not client or not verify_password(password, client.password_hash):
        raise ValueError("Email o clave incorrectos.")

    if not client.portal_active:
        raise PortalEmailPending(
            client.id,
            client.email or email,
            "Confirma tu correo con el código que te enviamos.",
        )
    return client
