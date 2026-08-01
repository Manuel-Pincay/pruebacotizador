"""Envío de factura autorizada por correo (PDF RIDE + XML)."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.models.sri_establishment import SriEstablishment
from app.services.email_service import EmailDeliveryError, send_email
from app.services.smtp_config_service import smtp_configured
from app.services.ride_pdf_service import generate_ride_pdf
from app.utils.activity import log_activity
from app.utils.client_emails import (
    collect_client_recipients,
    load_additional_emails,
    parse_additional_emails_raw,
    save_additional_emails,
)

DEFAULT_SUBJECT = "Factura electrónica {numero_factura} — {empresa}"
DEFAULT_BODY = """Estimado/a {cliente},

Adjuntamos su factura electrónica autorizada por el SRI.

Comprobante: {numero_factura}
Fecha de emisión: {fecha}
Total: {total}

Gracias por su preferencia.

{empresa}
"""


def _template_vars(invoice: ElectronicInvoice, config: CompanyConfig | None) -> dict:
    client = invoice.client
    cliente_nombre = (client.company or client.name or "Cliente") if client else "Cliente"
    empresa = (
        (config.sri_razon_social if config else None)
        or (config.company_name if config else None)
        or "Empresa"
    )
    fecha = invoice.fecha_emision.strftime("%d/%m/%Y") if invoice.fecha_emision else ""
    return {
        "cliente": cliente_nombre,
        "numero_factura": invoice.numero_comprobante,
        "fecha": fecha,
        "total": f"${float(invoice.importe_total or 0):.2f}",
        "empresa": empresa,
        "clave_acceso": invoice.clave_acceso or "",
    }


def render_template(template: str, variables: dict) -> str:
    text = template or ""
    for key, value in variables.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def get_default_subject(config: CompanyConfig | None) -> str:
    return (config.billing_email_subject if config and config.billing_email_subject else DEFAULT_SUBJECT).strip()


def get_default_body(config: CompanyConfig | None) -> str:
    return (config.billing_email_body if config and config.billing_email_body else DEFAULT_BODY).strip()


def should_auto_send(config: CompanyConfig | None) -> bool:
    if not config:
        return False
    return bool(config.billing_auto_send_email) and smtp_configured(config)


def load_merged_additional(client, new_list: list[str]) -> list[str]:
    existing = set(load_additional_emails(client))
    for email in parse_additional_emails_raw(",".join(new_list)):
        existing.add(email)
    return sorted(existing)


def send_invoice_email(
    db: Session,
    invoice_id: int,
    *,
    custom_message: str | None = None,
    extra_emails: list[str] | None = None,
    save_extra_to_client: list[str] | None = None,
    user_id=None,
) -> dict:
    invoice = (
        db.query(ElectronicInvoice)
        .options(joinedload(ElectronicInvoice.client), joinedload(ElectronicInvoice.lines))
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise ValueError("Factura no encontrada.")
    if invoice.estado != "AUTORIZADA":
        raise ValueError("Solo se puede enviar por correo una factura autorizada por el SRI.")

    config = db.query(CompanyConfig).first()
    client = invoice.client
    if not client:
        raise ValueError("La factura no tiene cliente asociado.")

    if save_extra_to_client:
        client.additional_emails_json = save_additional_emails(
            load_merged_additional(client, save_extra_to_client)
        )
        db.commit()
        db.refresh(client)

    recipients = collect_client_recipients(client, extra_emails)
    if not recipients:
        raise ValueError("El cliente no tiene correo electrónico. Regístrelo en la ficha del cliente.")

    xml_content = invoice.xml_autorizado or invoice.xml_firmado
    if not xml_content:
        raise ValueError("No hay XML autorizado para adjuntar.")

    dir_sucursal = None
    if invoice.codigo_establecimiento:
        est = (
            db.query(SriEstablishment)
            .filter(SriEstablishment.codigo == invoice.codigo_establecimiento)
            .first()
        )
        if est:
            dir_sucursal = est.direccion

    pdf_bytes = generate_ride_pdf(invoice, config, dir_sucursal=dir_sucursal)
    vars_ = _template_vars(invoice, config)
    subject = render_template(get_default_subject(config), vars_)
    body = (custom_message or "").strip() or render_template(get_default_body(config), vars_)

    xml_filename = f"factura_{invoice.numero_comprobante.replace('-', '_')}.xml"
    pdf_filename = f"RIDE_{invoice.numero_comprobante.replace('-', '_')}.pdf"

    try:
        send_email(
            to_addresses=recipients,
            subject=subject,
            body_text=body,
            attachments=[
                (pdf_filename, pdf_bytes, "application/pdf"),
                (xml_filename, xml_content.encode("utf-8"), "application/xml"),
            ],
            reply_to=(config.sri_email_notificacion if config else None) or None,
            config=config,
        )
    except EmailDeliveryError as exc:
        invoice.email_last_error = str(exc)
        db.commit()
        raise ValueError(str(exc)) from exc

    invoice.email_sent_at = datetime.utcnow()
    invoice.email_sent_to_json = json.dumps(recipients, ensure_ascii=False)
    invoice.email_last_error = None
    db.commit()

    log_activity(
        db,
        "FACTURA_EMAIL_ENVIADO",
        f"Factura #{invoice.id} enviada a {', '.join(recipients)}",
    )
    return {"success": True, "recipients": recipients, "invoice_id": invoice.id}


def try_auto_send_after_authorization(db: Session, invoice_id: int) -> None:
    """No interrumpe la autorización SRI si el correo falla."""
    config = db.query(CompanyConfig).first()
    if not should_auto_send(config):
        return
    try:
        send_invoice_email(db, invoice_id)
    except Exception as exc:
        invoice = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == invoice_id).first()
        if invoice:
            invoice.email_last_error = str(exc)
            db.commit()
        log_activity(db, "FACTURA_EMAIL_ERROR", f"Factura #{invoice_id}: {exc}")
