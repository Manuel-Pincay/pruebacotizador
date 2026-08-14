"""Envío SMTP (stdlib). Configuración en ERP o .env."""
from __future__ import annotations

import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Iterable

from app.services.smtp_config_service import SmtpSettings, resolve_smtp_settings


class EmailDeliveryError(Exception):
    pass


def _friendly_smtp_error(exc: Exception) -> str:
    raw = str(exc).lower()
    if "basic authentication is disabled" in raw or "5.7.139" in raw:
        return (
            "Microsoft (Outlook/Hotmail) rechazó el inicio de sesión.\n\n"
            "Causa: ya no acepta la contraseña normal de la cuenta por SMTP.\n\n"
            "Qué hacer:\n"
            "1. Use una contraseña de aplicación (no su contraseña de Hotmail).\n"
            "   → account.microsoft.com → Seguridad → Contraseñas de aplicación\n"
            "2. Active verificación en dos pasos si aún no la tiene.\n"
            "3. Si sigue fallando, Microsoft puede haber bloqueado SMTP en cuentas "
            "@hotmail/@outlook personales. En ese caso use Gmail con contraseña de "
            "aplicación o un servicio de correo para empresas (SendGrid, Brevo, etc.)."
        )
    if "535" in raw and ("authentication" in raw or "authenticate" in raw):
        return (
            "Correo o contraseña incorrectos.\n\n"
            "Verifique que el correo coincida con la cuenta y que use "
            "contraseña de aplicación, no la contraseña con la que entra al correo."
        )
    if "534" in raw or "application-specific password" in raw:
        return (
            "El proveedor exige contraseña de aplicación.\n"
            "Genere una en la configuración de seguridad de su correo e ingrésela en "
            "Configuración de empresa → Correo SMTP (o Facturación → Configuración SRI)."
        )
    if "connection refused" in raw or "timed out" in raw or "timeout" in raw:
        return (
            "No se pudo conectar al servidor SMTP.\n"
            "Revise host, puerto (587 con TLS o 465 con SSL) y firewall."
        )
    return str(exc)


def _open_smtp(smtp_settings: SmtpSettings) -> smtplib.SMTP:
    """Abre sesión SMTP: SSL implícito (465) o STARTTLS (587)."""
    host = smtp_settings.host
    port = int(smtp_settings.port or 587)
    use_ssl = port == 465

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=30)
        server.ehlo()
    elif smtp_settings.use_tls:
        server = smtplib.SMTP(host, port, timeout=30)
        server.ehlo()
        server.starttls()
        server.ehlo()
    else:
        server = smtplib.SMTP(host, port, timeout=30)
        server.ehlo()

    if smtp_settings.user:
        server.login(smtp_settings.user, smtp_settings.password or "")
    return server


def send_email(
    *,
    to_addresses: Iterable[str],
    subject: str,
    body_text: str,
    body_html: str | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
    reply_to: str | None = None,
    from_name: str | None = None,
    smtp: SmtpSettings | None = None,
    config=None,
) -> None:
    """
    attachments: lista de (filename, content_bytes, mime_type)
    """
    smtp_settings = smtp or resolve_smtp_settings(config)
    if not smtp_settings:
        raise EmailDeliveryError(
            "Correo no configurado. Complete SMTP en Configuración de empresa "
            "o en Facturación → Configuración SRI → Envío por correo."
        )

    recipients = [a.strip().lower() for a in to_addresses if a and a.strip()]
    if not recipients:
        raise EmailDeliveryError("No hay destinatarios válidos.")

    if body_html:
        msg = MIMEMultipart("alternative")
    else:
        msg = MIMEMultipart()

    display = (from_name or "").strip()
    msg["From"] = (
        formataddr((display, smtp_settings.from_addr))
        if display
        else smtp_settings.from_addr
    )
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    for filename, content, mime in attachments or []:
        maintype, _, subtype = (mime or "application/octet-stream").partition("/")
        part = MIMEBase(maintype, subtype or "octet-stream")
        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    try:
        server = _open_smtp(smtp_settings)
        try:
            server.sendmail(smtp_settings.from_addr, recipients, msg.as_string())
        finally:
            try:
                server.quit()
            except Exception:
                server.close()
    except EmailDeliveryError:
        raise
    except Exception as exc:
        raise EmailDeliveryError(_friendly_smtp_error(exc)) from exc


def send_test_email(
    *,
    smtp: SmtpSettings,
    to_address: str,
    company_name: str = "Su empresa",
) -> None:
    """Envía un correo de prueba para validar la configuración SMTP."""
    body = (
        "Este es un correo de prueba del ERP.\n\n"
        "Si recibió este mensaje, la configuración de correo está correcta.\n"
        "Se usará para facturas electrónicas y códigos de verificación de la tienda.\n\n"
        f"Remitente configurado: {smtp.from_addr}\n"
        f"Servidor: {smtp.host}:{smtp.port}\n\n"
        f"— {company_name}\n"
    )
    html = (
        f"<p>Este es un correo de prueba del ERP.</p>"
        f"<p>Si recibió este mensaje, la configuración de correo está correcta.</p>"
        f"<p>Se usará para <strong>facturas</strong> y "
        f"<strong>códigos de verificación de la tienda</strong>.</p>"
        f"<p style='color:#64748b;font-size:13px'>"
        f"Remitente: {smtp.from_addr}<br>Servidor: {smtp.host}:{smtp.port}</p>"
        f"<p>— {company_name}</p>"
    )
    send_email(
        to_addresses=[to_address],
        subject=f"Prueba de correo — {company_name}",
        body_text=body,
        body_html=html,
        from_name=company_name,
        smtp=smtp,
    )
