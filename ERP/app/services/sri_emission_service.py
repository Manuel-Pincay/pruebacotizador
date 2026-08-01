import json
import time
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.models.electronic_invoice_line import ElectronicInvoiceLine
from app.models.quotation import Quotation
from app.models.sri_certificate import SriCertificate
from app.models.sri_emission_point import SriEmissionPoint
from app.models.sri_establishment import SriEstablishment
from app.models.sri_sequence import SriSequence
from app.services.sri_client_service import (
    consultar_autorizacion,
    enviar_comprobante,
    format_sri_mensajes,
    humanize_sri_transport_error,
)
from app.services.invoice_service import ensure_clave_coherente_con_config
from app.services.sri_config_validator import ValidationIssue, validate_invoice_for_emission
from app.services.sri_sign_service import SriSignError, sign_comprobante_xml
from app.services.sri_xml_service import build_factura_xml, build_nota_credito_xml
from app.utils.encryption import decrypt_bytes, decrypt_text


def _company_dict(config: CompanyConfig) -> dict:
    return {
        "ruc": config.sri_ruc,
        "razon_social": config.sri_razon_social,
        "nombre_comercial": config.sri_nombre_comercial,
        "direccion_matriz": config.sri_direccion_matriz,
        "obligado_contabilidad": bool(config.sri_obligado_contabilidad),
        "contribuyente_especial": config.sri_contribuyente_especial,
        "contribuyente_rimpe": config.sri_contribuyente_rimpe,
        "ambiente": config.sri_ambiente or "PRUEBAS",
        "tipo_emision": config.sri_tipo_emision or "NORMAL",
    }


def _cliente_dict(client) -> dict:
    return {
        "tipo_identificacion": (client.tipo_identificacion or "CEDULA").upper(),
        "identificacion": (client.ruc_ci or "").strip(),
        "razon_social": (client.company or client.name or "").strip(),
        "direccion": client.address,
        "email": client.email,
        "telefono": client.phone,
    }


def _detalles_dict(lines) -> list:
    return [
        {
            "codigo_principal": line.codigo_principal,
            "codigo_auxiliar": line.codigo_auxiliar,
            "descripcion": line.descripcion,
            "cantidad": line.cantidad,
            "precio_unitario": line.precio_unitario,
            "descuento": line.descuento,
            "precio_total_sin_impuesto": line.precio_total_sin_impuesto,
            "codigo_iva": line.codigo_iva,
            "tarifa_iva": line.tarifa_iva,
            "valor_iva": line.valor_iva,
        }
        for line in lines
    ]


def _load_certificate(db: Session):
    cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
    if not cert:
        raise ValueError("Certificado electrónico no configurado.")
    return {
        "p12": decrypt_bytes(cert.encrypted_p12),
        "password": decrypt_text(cert.encrypted_password),
        "record": cert,
    }


def _cancelar_envio_pendiente(db: Session, invoice: ElectronicInvoice, mensajes_sri: dict, motivo: str):
    """Como FactuSRI: revierte a borrador para permitir corregir y reintentar."""
    invoice.estado = "BORRADOR"
    invoice.xml_generado = None
    invoice.xml_firmado = None
    invoice.error_message = humanize_sri_transport_error(motivo) if "SRI HTTP" in motivo else motivo
    invoice.mensajes_sri_json = json.dumps(mensajes_sri, ensure_ascii=False, default=str)
    db.commit()


def _try_recuperar_desde_sri(db: Session, invoice: ElectronicInvoice, ambiente: str, tipo_emision: str = "NORMAL"):
    """Si un envío falló con HTTP 5xx, el SRI pudo haber recibido el comprobante igual."""
    if not invoice.clave_acceso:
        return None
    autorizacion = consultar_autorizacion(invoice.clave_acceso, ambiente, tipo_emision)
    estado = autorizacion.get("estado")
    if estado == "AUTORIZADO":
        return _apply_autorizacion(db, invoice, autorizacion)
    if estado == "EN PROCESO":
        invoice.estado = "RECIBIDA"
        invoice.error_message = "Comprobante en proceso en el SRI. Consulte autorización en unos minutos."
        invoice.mensajes_sri_json = json.dumps(autorizacion, ensure_ascii=False, default=str)
        db.commit()
        return {
            "success": False,
            "estado": invoice.estado,
            "message": invoice.error_message,
            "invoice": invoice,
        }
    return None


def _build_xml(invoice: ElectronicInvoice, config: CompanyConfig, db: Session) -> str:
    est = (
        db.query(SriEstablishment)
        .filter(SriEstablishment.codigo == invoice.codigo_establecimiento)
        .first()
    )
    dir_est = est.direccion if est else config.sri_direccion_matriz
    info = json.loads(invoice.info_adicional_json) if invoice.info_adicional_json else None
    company = _company_dict(config)
    cliente = _cliente_dict(invoice.client)
    detalles = _detalles_dict(invoice.lines)

    if (invoice.tipo_comprobante or "FACTURA").upper() == "NOTA_CREDITO":
        return build_nota_credito_xml(
            company,
            {
                "clave_acceso": invoice.clave_acceso,
                "secuencial": invoice.secuencial,
                "codigo_establecimiento": invoice.codigo_establecimiento,
                "codigo_punto_emision": invoice.codigo_punto_emision,
                "fecha_emision": invoice.fecha_emision,
                "subtotal_sin_impuestos": invoice.subtotal_sin_impuestos,
                "subtotal_iva": invoice.subtotal_iva,
                "descuento": invoice.descuento,
                "importe_total": invoice.importe_total,
                "dir_establecimiento": dir_est,
                "info_adicional": info,
                "cod_doc_modificado": invoice.cod_doc_modificado or "01",
                "num_doc_modificado": invoice.num_doc_modificado or "",
                "fecha_emision_doc_sustento": invoice.fecha_emision_doc_sustento or invoice.fecha_emision,
                "motivo": invoice.motivo or "ANULACIÓN DE FACTURA",
            },
            cliente,
            detalles,
        )

    pagos = json.loads(invoice.pagos_json) if invoice.pagos_json else None
    return build_factura_xml(
        company,
        {
            "clave_acceso": invoice.clave_acceso,
            "secuencial": invoice.secuencial,
            "codigo_establecimiento": invoice.codigo_establecimiento,
            "codigo_punto_emision": invoice.codigo_punto_emision,
            "fecha_emision": invoice.fecha_emision,
            "subtotal_sin_impuestos": invoice.subtotal_sin_impuestos,
            "subtotal_iva": invoice.subtotal_iva,
            "descuento": invoice.descuento,
            "propina": invoice.propina,
            "importe_total": invoice.importe_total,
            "dir_establecimiento": dir_est,
            "pagos": pagos,
            "info_adicional": info,
        },
        cliente,
        detalles,
    )


def _poll_autorizacion(clave_acceso: str, ambiente: str, tipo_emision: str = "NORMAL", retries=5, delay=2):
    auth = consultar_autorizacion(clave_acceso, ambiente, tipo_emision)
    for _ in range(retries):
        if auth.get("estado") != "EN PROCESO":
            break
        time.sleep(delay)
        auth = consultar_autorizacion(clave_acceso, ambiente, tipo_emision)
    return auth


def emit_invoice(db: Session, invoice_id: int, user_id=None) -> dict:
    invoice = (
        db.query(ElectronicInvoice)
        .options(
            joinedload(ElectronicInvoice.client),
            joinedload(ElectronicInvoice.lines),
        )
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise ValueError("Factura no encontrada.")

    if invoice.estado == "AUTORIZADA":
        tipo = "nota de crédito" if invoice.is_nota_credito else "factura"
        raise ValueError(f"La {tipo} ya está autorizada.")

    if invoice.estado in ("RECIBIDA", "ENVIANDO") and invoice.clave_acceso:
        invoice = (
            db.query(ElectronicInvoice)
            .options(joinedload(ElectronicInvoice.client), joinedload(ElectronicInvoice.lines))
            .filter(ElectronicInvoice.id == invoice_id)
            .first()
        )
        return sync_invoice_from_sri(db, invoice_id)

    config = db.query(CompanyConfig).first()
    cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
    validation = validate_invoice_for_emission(db, invoice, config, cert)
    if not validation.valido:
        msgs = [e.mensaje for e in validation.errores]
        raise ValueError("No se puede emitir la factura:\n" + "\n".join(f"• {m}" for m in msgs))

    invoice = ensure_clave_coherente_con_config(db, invoice, config)
    invoice = (
        db.query(ElectronicInvoice)
        .options(joinedload(ElectronicInvoice.client), joinedload(ElectronicInvoice.lines))
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )

    ambiente = config.sri_ambiente or "PRUEBAS"
    tipo_emision = config.sri_tipo_emision or "NORMAL"

    if invoice.error_message and "SRI HTTP 5" in invoice.error_message:
        from app.services.invoice_service import regenerar_clave_borrador

        regenerar_clave_borrador(db, invoice_id, user_id=user_id)
        invoice = (
            db.query(ElectronicInvoice)
            .options(joinedload(ElectronicInvoice.client), joinedload(ElectronicInvoice.lines))
            .filter(ElectronicInvoice.id == invoice_id)
            .first()
        )
    else:
        recovered = _try_recuperar_desde_sri(db, invoice, ambiente, tipo_emision)
        if recovered:
            return recovered

    xml_generado = _build_xml(invoice, config, db)
    invoice.xml_generado = xml_generado
    invoice.estado = "PENDIENTE_ENVIO"
    db.commit()

    cert_data = _load_certificate(db)
    invoice.estado = "ENVIANDO"
    db.commit()

    try:
        xml_firmado = sign_comprobante_xml(
            xml_generado, cert_data["p12"], cert_data["password"], invoice.tipo_comprobante or "FACTURA"
        )
    except SriSignError as exc:
        invoice.estado = "BORRADOR"
        invoice.error_message = str(exc)
        invoice.xml_firmado = None
        db.commit()
        raise ValueError(f"Error al firmar XML: {exc}") from exc

    invoice.xml_firmado = xml_firmado
    db.commit()

    try:
        recepcion = enviar_comprobante(xml_firmado, ambiente, tipo_emision)
    except Exception as exc:
        detail = str(exc)
        recovered = _try_recuperar_desde_sri(db, invoice, ambiente, tipo_emision)
        if recovered and recovered.get("success"):
            return recovered
        _cancelar_envio_pendiente(
            db,
            invoice,
            {"fase": "RECEPCION", "error": detail},
            detail,
        )
        raise ValueError(f"No se pudo enviar al SRI: {humanize_sri_transport_error(detail)}") from exc

    if recepcion.get("estado") != "RECIBIDA":
        msg = format_sri_mensajes(recepcion.get("mensajes"), recepcion.get("estado"))
        _cancelar_envio_pendiente(
            db,
            invoice,
            {"fase": "RECEPCION", **recepcion},
            f"El SRI rechazó la recepción: {msg}",
        )
        raise ValueError(f"El SRI rechazó la recepción: {msg}")

    invoice.estado = "RECIBIDA"
    invoice.mensajes_sri_json = json.dumps(recepcion, ensure_ascii=False, default=str)
    db.commit()

    try:
        autorizacion = _poll_autorizacion(invoice.clave_acceso, ambiente, tipo_emision)
    except Exception as exc:
        invoice.error_message = f"Enviada pero no se pudo consultar autorización: {exc}"
        db.commit()
        return {"success": False, "estado": invoice.estado, "message": invoice.error_message, "invoice": invoice}

    return _apply_autorizacion(db, invoice, autorizacion)


def _apply_autorizacion(db: Session, invoice: ElectronicInvoice, autorizacion: dict) -> dict:
    estado = autorizacion.get("estado")
    if estado == "AUTORIZADO":
        invoice.estado = "AUTORIZADA"
        invoice.numero_autorizacion = autorizacion.get("numero_autorizacion") or invoice.clave_acceso
        fecha = autorizacion.get("fecha_autorizacion")
        if fecha:
            try:
                invoice.fecha_autorizacion = datetime.fromisoformat(str(fecha).replace("Z", "+00:00"))
            except ValueError:
                invoice.fecha_autorizacion = datetime.utcnow()
        else:
            invoice.fecha_autorizacion = datetime.utcnow()
        invoice.xml_autorizado = autorizacion.get("comprobante_xml") or invoice.xml_firmado
        invoice.mensajes_sri_json = json.dumps(autorizacion, ensure_ascii=False, default=str)
        invoice.error_message = None
        db.commit()
        db.refresh(invoice)
        if invoice.is_nota_credito:
            from app.services.credit_note_service import mark_invoice_annulled_by_credit_note

            mark_invoice_annulled_by_credit_note(db, invoice)
        else:
            from app.services.invoice_email_service import try_auto_send_after_authorization

            try_auto_send_after_authorization(db, invoice.id)
        return {"success": True, "estado": "AUTORIZADA", "invoice": invoice, "autorizacion": autorizacion}

    if estado in ("NO AUTORIZADO", "RECHAZADO"):
        invoice.estado = "RECHAZADA"
        invoice.error_message = format_sri_mensajes(autorizacion.get("mensajes"), estado)
        invoice.mensajes_sri_json = json.dumps(autorizacion, ensure_ascii=False, default=str)
        db.commit()
        raise ValueError(f"El SRI no autorizó el comprobante: {invoice.error_message}")

    invoice.mensajes_sri_json = json.dumps(autorizacion, ensure_ascii=False, default=str)
    db.commit()
    return {
        "success": False,
        "estado": invoice.estado,
        "message": "Comprobante en proceso de autorización. Consulte nuevamente en unos minutos.",
        "invoice": invoice,
        "autorizacion": autorizacion,
    }


def sync_invoice_from_sri(db: Session, invoice_id: int) -> dict:
    invoice = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Factura no encontrada.")
    config = db.query(CompanyConfig).first()
    ambiente = (config.sri_ambiente if config else None) or "PRUEBAS"
    tipo_emision = (config.sri_tipo_emision if config else None) or "NORMAL"
    autorizacion = _poll_autorizacion(invoice.clave_acceso, ambiente, tipo_emision)
    return _apply_autorizacion(db, invoice, autorizacion)


def validate_invoice_emission(db: Session, invoice_id: int):
    """Validación previa a emisión (como FactuSRI GET .../validar)."""
    invoice = (
        db.query(ElectronicInvoice)
        .options(joinedload(ElectronicInvoice.client), joinedload(ElectronicInvoice.lines))
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )
    if not invoice:
        raise ValueError("Factura no encontrada.")
    config = db.query(CompanyConfig).first()
    cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
    result = validate_invoice_for_emission(db, invoice, config, cert)
    if result.valido:
        try:
            _build_xml(invoice, config, db)
        except Exception as exc:
            result.errores.append(ValidationIssue("factura.xml", str(exc)))
            result.valido = False
    return result
