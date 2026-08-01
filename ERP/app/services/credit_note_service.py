"""Notas de crédito — creación desde factura autorizada."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session, joinedload

from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.models.electronic_invoice_line import ElectronicInvoiceLine
from app.services.sri_config_validator import ValidationIssue, ValidationResult, validate_sri_config
from app.services.sri_sequence_service import reserve_clave_acceso
from app.utils.activity import log_activity
from app.utils.datetime_ec import now_ecuador


def _load_invoice(db: Session, invoice_id: int) -> ElectronicInvoice | None:
    return (
        db.query(ElectronicInvoice)
        .options(
            joinedload(ElectronicInvoice.client),
            joinedload(ElectronicInvoice.lines),
            joinedload(ElectronicInvoice.notas_credito),
        )
        .filter(ElectronicInvoice.id == invoice_id)
        .first()
    )


def get_authorized_credit_note(invoice: ElectronicInvoice) -> ElectronicInvoice | None:
    for nc in invoice.notas_credito or []:
        if nc.estado == "AUTORIZADA":
            return nc
    return None


def get_pending_credit_note(invoice: ElectronicInvoice) -> ElectronicInvoice | None:
    for nc in invoice.notas_credito or []:
        if nc.estado not in ("RECHAZADA", "ANULADA", "ERROR"):
            return nc
    return None


def validate_credit_note_creation(db: Session, invoice: ElectronicInvoice, motivo: str) -> ValidationResult:
    result = ValidationResult()
    config = db.query(CompanyConfig).first()
    if config:
        result.errores.extend(validate_sri_config(db, config, None).errores)

    if not invoice:
        result.errores.append(ValidationIssue("factura", "Factura no encontrada."))
        result.valido = False
        return result

    if not invoice.is_factura:
        result.errores.append(ValidationIssue("factura.tipo", "Solo se puede anular facturas con nota de crédito."))

    if invoice.estado != "AUTORIZADA":
        result.errores.append(
            ValidationIssue("factura.estado", "Solo facturas autorizadas por el SRI pueden anularse con nota de crédito.")
        )

    if invoice.estado == "ANULADA":
        result.errores.append(ValidationIssue("factura.estado", "Esta factura ya está anulada."))

    if get_authorized_credit_note(invoice):
        result.errores.append(ValidationIssue("nota_credito", "Ya existe una nota de crédito autorizada para esta factura."))

    pending = get_pending_credit_note(invoice)
    if pending and pending.estado != "AUTORIZADA":
        result.errores.append(
            ValidationIssue(
                "nota_credito",
                f"Ya hay una nota de crédito en estado {pending.estado}. "
                f"Emítala o anúlela antes de crear otra.",
            )
        )

    motivo_clean = (motivo or "").strip()
    if not motivo_clean:
        result.errores.append(ValidationIssue("motivo", "Indique el motivo de la nota de crédito."))
    elif len(motivo_clean) > 300:
        result.errores.append(ValidationIssue("motivo", "El motivo no puede superar 300 caracteres."))

    if not invoice.lines:
        result.errores.append(ValidationIssue("factura.detalles", "La factura no tiene líneas para devolver."))

    result.valido = len(result.errores) == 0
    return result


def build_credit_note_preview(db: Session, invoice_id: int, motivo: str) -> dict:
    invoice = _load_invoice(db, invoice_id)
    if not invoice:
        raise ValueError("Factura no encontrada.")
    validation = validate_credit_note_creation(db, invoice, motivo)
    return {
        "invoice": invoice,
        "motivo": (motivo or "").strip(),
        "validation": validation,
        "existing_nc": get_pending_credit_note(invoice),
    }


def create_credit_note_from_invoice(
    db: Session,
    invoice_id: int,
    motivo: str,
    user_id=None,
) -> ElectronicInvoice:
    invoice = _load_invoice(db, invoice_id)
    if not invoice:
        raise ValueError("Factura no encontrada.")

    validation = validate_credit_note_creation(db, invoice, motivo)
    if not validation.valido:
        from app.services.sri_config_validator import format_validation_errors

        raise ValueError(format_validation_errors(validation))

    pending = get_pending_credit_note(invoice)
    if pending and pending.estado == "BORRADOR":
        pending.motivo = motivo.strip()
        db.commit()
        db.refresh(pending)
        return pending

    config = db.query(CompanyConfig).first()
    if not config:
        raise ValueError("Configure la empresa SRI antes de continuar.")

    fecha = now_ecuador()
    secuencial, clave = reserve_clave_acceso(
        db,
        config,
        invoice.codigo_establecimiento,
        invoice.codigo_punto_emision,
        fecha,
        tipo="NOTA_CREDITO",
    )

    info = json.loads(invoice.info_adicional_json) if invoice.info_adicional_json else []
    info = list(info)
    info.append({"nombre": "FacturaModificada", "valor": invoice.numero_comprobante})

    nc = ElectronicInvoice(
        client_id=invoice.client_id,
        created_by_user_id=user_id,
        tipo_comprobante="NOTA_CREDITO",
        clave_acceso=clave,
        secuencial=secuencial,
        codigo_establecimiento=invoice.codigo_establecimiento,
        codigo_punto_emision=invoice.codigo_punto_emision,
        fecha_emision=fecha,
        subtotal_sin_impuestos=invoice.subtotal_sin_impuestos,
        subtotal_iva=invoice.subtotal_iva,
        descuento=invoice.descuento,
        propina=0,
        importe_total=invoice.importe_total,
        pagos_json=None,
        info_adicional_json=json.dumps(info, ensure_ascii=False),
        estado="BORRADOR",
        invoice_modificado_id=invoice.id,
        motivo=motivo.strip(),
        cod_doc_modificado="01",
        num_doc_modificado=invoice.numero_comprobante,
        fecha_emision_doc_sustento=invoice.fecha_emision,
    )
    db.add(nc)
    db.flush()

    for line in invoice.lines:
        db.add(
            ElectronicInvoiceLine(
                invoice_id=nc.id,
                product_id=line.product_id,
                quotation_item_id=line.quotation_item_id,
                codigo_principal=line.codigo_principal,
                codigo_auxiliar=line.codigo_auxiliar,
                descripcion=line.descripcion,
                cantidad=line.cantidad,
                precio_unitario=line.precio_unitario,
                descuento=line.descuento,
                precio_total_sin_impuesto=line.precio_total_sin_impuesto,
                codigo_iva=line.codigo_iva,
                tarifa_iva=line.tarifa_iva,
                valor_iva=line.valor_iva,
            )
        )

    db.commit()
    db.refresh(nc)
    log_activity(
        db,
        "NOTA_CREDITO_CREADA",
        f"NC #{nc.id} para factura #{invoice.id} — {invoice.numero_comprobante}",
    )
    return nc


def mark_invoice_annulled_by_credit_note(db: Session, credit_note: ElectronicInvoice) -> None:
    if not credit_note.invoice_modificado_id:
        return
    original = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == credit_note.invoice_modificado_id).first()
    if original and original.estado == "AUTORIZADA":
        original.estado = "ANULADA"
        db.commit()
        log_activity(
            db,
            "FACTURA_ANULADA_NC",
            f"Factura #{original.id} anulada por NC #{credit_note.id}",
        )
