import json
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.models.electronic_invoice_line import ElectronicInvoiceLine
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.sri_certificate import SriCertificate
from app.services.sri_sequence_service import peek_next_secuencial, reserve_clave_acceso, update_sequence_manual
from app.services.sri_config_validator import (
    ValidationIssue,
    ValidationResult,
    validate_client_for_invoice,
    validate_sri_config,
)
from app.utils.clave_acceso import ambiente_desde_clave, generar_clave_acceso
from app.services.tax_service import (
    compute_invoice_totals,
    default_sri_tarifa_from_config,
    quotation_item_to_line,
    round2,
)
from app.utils.activity import log_activity
from app.utils.datetime_ec import now_ecuador

QUOTATION_BILLABLE_STATUSES = (
    "aprobada",
    "produccion",
    "enviado",
    "enviada",
    "entregado",
    "entregada",
)


def _default_estab_pto(config: CompanyConfig):
    estab = (config.sri_default_establishment or "001").zfill(3)[-3:]
    pto = (config.sri_default_emission_point or "001").zfill(3)[-3:]
    return estab, pto


def _create_invoice_from_lines(
    db: Session,
    client_id: int,
    lines_data: list,
    config: CompanyConfig,
    quotation_id=None,
    user_id=None,
    descuento_global=0,
    propina=0,
    info_adicional=None,
    codigo_establecimiento: str | None = None,
    codigo_punto_emision: str | None = None,
    pagos: list | None = None,
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError("Cliente no encontrado.")

    totals = compute_invoice_totals(lines_data, descuento_global, propina)
    estab, pto = _default_estab_pto(config)
    if codigo_establecimiento:
        estab = str(codigo_establecimiento).zfill(3)[-3:]
    if codigo_punto_emision:
        pto = str(codigo_punto_emision).zfill(3)[-3:]

    if not pagos:
        pagos = [
            {
                "forma_pago": "01",
                "total": totals["importe_total"],
                "plazo": "0",
                "unidad_tiempo": "Dias",
            }
        ]
    total_pagos = round(sum(float(p.get("total") or 0) for p in pagos), 2)
    if abs(total_pagos - totals["importe_total"]) > 0.01:
        raise ValueError(
            f"Las formas de pago deben sumar el total (${totals['importe_total']:.2f}). "
            f"Suma actual: ${total_pagos:.2f}."
        )

    fecha = now_ecuador()
    secuencial, clave = reserve_clave_acceso(db, config, estab, pto, fecha)

    invoice = ElectronicInvoice(
        quotation_id=quotation_id,
        client_id=client_id,
        created_by_user_id=user_id,
        clave_acceso=clave,
        secuencial=secuencial,
        codigo_establecimiento=estab,
        codigo_punto_emision=pto,
        fecha_emision=fecha,
        subtotal_sin_impuestos=totals["subtotal_sin_impuestos"],
        subtotal_iva=totals["subtotal_iva"],
        descuento=totals["descuento"],
        propina=totals["propina"],
        importe_total=totals["importe_total"],
        pagos_json=json.dumps(pagos, ensure_ascii=False),
        info_adicional_json=json.dumps(info_adicional or [], ensure_ascii=False) if info_adicional else None,
        estado="BORRADOR",
    )
    db.add(invoice)
    db.flush()

    for line in lines_data:
        db.add(
            ElectronicInvoiceLine(
                invoice_id=invoice.id,
                product_id=line.get("product_id"),
                quotation_item_id=line.get("quotation_item_id"),
                codigo_principal=line["codigo_principal"],
                codigo_auxiliar=line.get("codigo_auxiliar"),
                descripcion=line["descripcion"],
                cantidad=line["cantidad"],
                precio_unitario=line["precio_unitario"],
                descuento=line["descuento"],
                precio_total_sin_impuesto=line["precio_total_sin_impuesto"],
                codigo_iva=line["codigo_iva"],
                tarifa_iva=line["tarifa_iva"],
                valor_iva=line["valor_iva"],
            )
        )

    db.commit()
    db.refresh(invoice)
    return invoice


def _quotation_lines_data(quotation: Quotation, config: CompanyConfig) -> list:
    """Líneas fiscales SRI desde cotización (aplica sri_iva_default, no el IVA comercial)."""
    sri_tarifa = default_sri_tarifa_from_config(config)
    return [
        quotation_item_to_line(
            item,
            quotation.discount or 0,
            sri_tarifa,
            apply_sri_billing_iva=True,
        )
        for item in quotation.items
    ]


def _quotation_info_adicional(quotation: Quotation) -> list:
    info = [{"nombre": "Cotizacion", "valor": str(quotation.id)}]
    client = quotation.client
    if client:
        if client.phone:
            info.append({"nombre": "Telefono", "valor": client.phone})
        if client.address:
            info.append({"nombre": "Direccion", "valor": client.address})
        if client.email:
            info.append({"nombre": "Email", "valor": client.email})
    info.append({"nombre": "Condicion de Pago", "valor": "Contado"})
    return info


def validate_quotation_for_billing(db: Session, quotation: Quotation) -> ValidationResult:
    """Revisa datos fiscales antes de crear la factura (sin modificar la cotización)."""
    result = ValidationResult()
    config = db.query(CompanyConfig).first()
    cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()

    if quotation.status not in QUOTATION_BILLABLE_STATUSES:
        result.errores.append(
            ValidationIssue(
                "cotizacion.estado",
                "Solo se pueden facturar cotizaciones aprobadas o en proceso "
                "(diseño/producción/envío/entrega). Facturar no cambia el estado de trabajo.",
            )
        )
    if quotation.electronic_invoice:
        result.errores.append(
            ValidationIssue("cotizacion.factura", "Esta cotización ya tiene una factura asociada.")
        )
    if quotation.payment_status != "pagada":
        if quotation.payment_status == "sin_abono":
            msg = "La cotización debe estar pagada antes de facturar. Registre el pago completo."
        else:
            msg = "La cotización tiene abono parcial. Debe estar pagada por completo antes de facturar."
        result.errores.append(ValidationIssue("cotizacion.pago", msg))
    if not quotation.items:
        result.errores.append(
            ValidationIssue("cotizacion.items", "La cotización no tiene productos para facturar.")
        )

    if config:
        sri_result = validate_sri_config(db, config, cert)
        result.errores.extend(sri_result.errores)
        result.advertencias.extend(sri_result.advertencias)
        sri_tarifa = default_sri_tarifa_from_config(config)
    else:
        result.errores.append(
            ValidationIssue("sri.config", "Configure la empresa emisora SRI antes de facturar.")
        )
        sri_tarifa = 15.0

    if quotation.client:
        client_result = validate_client_for_invoice(quotation.client)
        result.errores.extend(client_result.errores)
        result.advertencias.extend(client_result.advertencias)
    else:
        result.errores.append(ValidationIssue("cliente", "La cotización no tiene cliente asociado."))

    for i, item in enumerate(quotation.items or []):
        prefix = f"items[{i}]"
        product = getattr(item, "product", None)
        descripcion = (
            getattr(item, "detail", None)
            or (getattr(product, "name", None) if product else None)
            or f"Ítem {item.id}"
        )
        if not product:
            result.advertencias.append(
                ValidationIssue(
                    f"{prefix}.producto",
                    f"'{descripcion}' no está vinculado a un producto del catálogo. "
                    f"Se usará un código generado (COT-{{id}}) e IVA SRI {sri_tarifa:g}%.",
                )
            )
        else:
            if not (getattr(product, "code", None) or "").strip():
                result.advertencias.append(
                    ValidationIssue(
                        f"{prefix}.codigo",
                        f"El producto '{product.name}' no tiene código; se usará COT-{item.id}. "
                        "Edite el producto en el catálogo antes de emitir.",
                    )
                )

    if quotation.items and config:
        lines = _quotation_lines_data(quotation, config)
        totals = compute_invoice_totals(lines)
        if totals["importe_total"] <= 0:
            result.errores.append(
                ValidationIssue("cotizacion.total", "El total a facturar debe ser mayor a cero.")
            )

    result.valido = len(result.errores) == 0
    return result


def build_quotation_invoice_preview(db: Session, quotation_id: int) -> dict:
    quotation = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.client),
            joinedload(Quotation.items).joinedload(QuotationItem.product),
            joinedload(Quotation.payments),
            joinedload(Quotation.electronic_invoice),
        )
        .filter(Quotation.id == quotation_id)
        .first()
    )
    if not quotation:
        raise ValueError("Cotización no encontrada.")

    config = db.query(CompanyConfig).first()
    if not config:
        raise ValueError("Configure la empresa antes de facturar.")

    validation = validate_quotation_for_billing(db, quotation)
    lines = _quotation_lines_data(quotation, config)
    totals = compute_invoice_totals(lines)

    preview_lines = []
    for line in lines:
        preview_lines.append(
            {
                **line,
                "line_total": round2(line["precio_total_sin_impuesto"] + line["valor_iva"]),
            }
        )

    return {
        "quotation": quotation,
        "lines": preview_lines,
        "totals": totals,
        "validation": validation,
        "info_adicional": _quotation_info_adicional(quotation),
        "config": config,
    }


def create_invoice_from_quotation(
    db: Session,
    quotation_id: int,
    user_id=None,
    *,
    pagos: list | None = None,
    skip_validation: bool = False,
) -> ElectronicInvoice:
    quotation = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.client),
            joinedload(Quotation.items).joinedload(QuotationItem.product),
            joinedload(Quotation.payments),
            joinedload(Quotation.electronic_invoice),
        )
        .filter(Quotation.id == quotation_id)
        .first()
    )
    if not quotation:
        raise ValueError("Cotización no encontrada.")

    if not skip_validation:
        validation = validate_quotation_for_billing(db, quotation)
        if not validation.valido:
            from app.services.sri_config_validator import format_validation_errors

            raise ValueError(format_validation_errors(validation))

    config = db.query(CompanyConfig).first()
    if not config:
        raise ValueError("Configure la empresa antes de facturar.")

    lines = _quotation_lines_data(quotation, config)
    if not lines:
        raise ValueError("La cotización no tiene líneas para facturar.")

    info = _quotation_info_adicional(quotation)
    invoice = _create_invoice_from_lines(
        db,
        quotation.client_id,
        lines,
        config,
        quotation_id=quotation.id,
        user_id=user_id,
        info_adicional=info,
        pagos=pagos,
    )
    log_activity(db, "FACTURA_CREADA", f"Factura #{invoice.id} desde cotización #{quotation_id}")
    return invoice


def create_manual_invoice(
    db: Session,
    client_id: int,
    items: list,
    user_id=None,
    descuento_global=0,
    *,
    codigo_establecimiento: str | None = None,
    codigo_punto_emision: str | None = None,
    pagos: list | None = None,
    info_adicional: list | None = None,
) -> ElectronicInvoice:
    config = db.query(CompanyConfig).first()
    if not config:
        raise ValueError("Configure la empresa antes de facturar.")

    if not items:
        raise ValueError("Agregue al menos un producto o línea a la factura.")

    from app.services.tax_service import compute_line, parse_tarifa_iva

    lines_data = []
    for item in items:
        calc = compute_line(
            item.get("cantidad", 1),
            item.get("precio_unitario", 0),
            item.get("descuento", 0),
            parse_tarifa_iva(item.get("tarifa_iva")),
            item.get("codigo_iva"),
        )
        lines_data.append(
            {
                "product_id": item.get("product_id"),
                "codigo_principal": (item.get("codigo_principal") or "MANUAL")[:50],
                "codigo_auxiliar": item.get("codigo_auxiliar"),
                "descripcion": (item.get("descripcion") or "Producto")[:500],
                "cantidad": float(item.get("cantidad", 1)),
                "precio_unitario": float(item.get("precio_unitario", 0)),
                "descuento": float(item.get("descuento", 0)),
                **calc,
            }
        )

    invoice = _create_invoice_from_lines(
        db,
        client_id,
        lines_data,
        config,
        user_id=user_id,
        descuento_global=descuento_global,
        codigo_establecimiento=codigo_establecimiento,
        codigo_punto_emision=codigo_punto_emision,
        pagos=pagos,
        info_adicional=info_adicional,
    )
    log_activity(db, "FACTURA_CREADA", f"Factura manual #{invoice.id}")
    return invoice


def ensure_clave_coherente_con_config(db: Session, invoice: ElectronicInvoice, config: CompanyConfig) -> ElectronicInvoice:
    """Regenera clave si el ambiente en clave no coincide con la config (como al cambiar PRUEBAS→PRODUCCIÓN)."""
    expected = (config.sri_ambiente or "PRUEBAS").upper()
    actual = ambiente_desde_clave(invoice.clave_acceso)
    if actual and actual != expected:
        invoice.clave_acceso = generar_clave_acceso(
            fecha_emision=invoice.fecha_emision,
            tipo_comprobante=invoice.tipo_comprobante or "FACTURA",
            ruc=config.sri_ruc,
            ambiente=expected,
            codigo_establecimiento=invoice.codigo_establecimiento,
            codigo_punto_emision=invoice.codigo_punto_emision,
            secuencial=invoice.secuencial,
            tipo_emision=config.sri_tipo_emision or "NORMAL",
        )
        invoice.error_message = None
        invoice.mensajes_sri_json = None
        invoice.xml_generado = None
        invoice.xml_firmado = None
        db.commit()
        db.refresh(invoice)
    return invoice


def anular_invoice(db: Session, invoice_id: int, user_id=None) -> ElectronicInvoice:
    invoice = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Factura no encontrada.")
    if invoice.estado == "ANULADA":
        raise ValueError("Esta factura ya está anulada.")
    if invoice.estado == "AUTORIZADA":
        raise ValueError(
            "Las facturas autorizadas no se anulan aquí: requieren nota de crédito ante el SRI (próximamente)."
        )
    if invoice.estado in ("ENVIANDO", "RECIBIDA"):
        raise ValueError("Consulte la autorización en el SRI antes de anular.")
    if invoice.estado not in ("BORRADOR", "RECHAZADA", "ERROR", "PENDIENTE_ENVIO"):
        raise ValueError(f"No se puede anular una factura en estado {invoice.estado}.")

    invoice.estado = "ANULADA"
    db.commit()
    db.refresh(invoice)
    log_activity(db, "FACTURA_ANULADA", f"Factura #{invoice.id} — {invoice.numero_comprobante}")
    return invoice


def regenerar_clave_borrador(db: Session, invoice_id: int, user_id=None) -> ElectronicInvoice:
    """Nueva clave de acceso con el mismo secuencial (útil tras HTTP 500 por reintento)."""
    invoice = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Factura no encontrada.")
    if invoice.estado != "BORRADOR":
        raise ValueError("Solo se puede regenerar la clave en borrador.")

    config = db.query(CompanyConfig).first()
    if not config:
        raise ValueError("Configure la empresa SRI antes de continuar.")

    anterior = invoice.clave_acceso
    invoice.clave_acceso = generar_clave_acceso(
        fecha_emision=invoice.fecha_emision,
        tipo_comprobante=invoice.tipo_comprobante or "FACTURA",
        ruc=config.sri_ruc,
        ambiente=config.sri_ambiente or "PRUEBAS",
        codigo_establecimiento=invoice.codigo_establecimiento,
        codigo_punto_emision=invoice.codigo_punto_emision,
        secuencial=invoice.secuencial,
        tipo_emision=config.sri_tipo_emision or "NORMAL",
    )
    invoice.error_message = None
    invoice.mensajes_sri_json = None
    invoice.xml_generado = None
    invoice.xml_firmado = None
    db.commit()
    db.refresh(invoice)
    log_activity(db, "FACTURA_CLAVE_REGENERADA", f"Factura #{invoice.id}: clave actualizada")
    return invoice


def renumerar_borrador(db: Session, invoice_id: int, user_id=None) -> ElectronicInvoice:
    """Asigna el siguiente secuencial libre cuando el SRI rechazó por número ya registrado."""
    invoice = db.query(ElectronicInvoice).filter(ElectronicInvoice.id == invoice_id).first()
    if not invoice:
        raise ValueError("Factura no encontrada.")
    if invoice.estado != "BORRADOR":
        raise ValueError("Solo se puede renumerar una factura en borrador.")
    if invoice.estado == "AUTORIZADA":
        raise ValueError("La factura ya está autorizada.")

    config = db.query(CompanyConfig).first()
    if not config:
        raise ValueError("Configure la empresa SRI antes de renumerar.")

    nuevo = peek_next_secuencial(
        db, invoice.codigo_establecimiento, invoice.codigo_punto_emision, invoice.tipo_comprobante or "FACTURA"
    )
    if nuevo == invoice.secuencial:
        update_sequence_manual(
            db,
            _emission_point_id(db, invoice.codigo_establecimiento, invoice.codigo_punto_emision),
            int(nuevo) + 1,
            invoice.tipo_comprobante or "FACTURA",
        )
        nuevo = peek_next_secuencial(
            db, invoice.codigo_establecimiento, invoice.codigo_punto_emision, invoice.tipo_comprobante or "FACTURA"
        )

    anterior = invoice.numero_comprobante
    invoice.secuencial = nuevo
    invoice.clave_acceso = generar_clave_acceso(
        fecha_emision=invoice.fecha_emision,
        tipo_comprobante=invoice.tipo_comprobante or "FACTURA",
        ruc=config.sri_ruc,
        ambiente=config.sri_ambiente or "PRUEBAS",
        codigo_establecimiento=invoice.codigo_establecimiento,
        codigo_punto_emision=invoice.codigo_punto_emision,
        secuencial=nuevo,
        tipo_emision=config.sri_tipo_emision or "NORMAL",
    )
    invoice.error_message = None
    invoice.mensajes_sri_json = None
    invoice.xml_generado = None
    invoice.xml_firmado = None
    update_sequence_manual(
        db,
        _emission_point_id(db, invoice.codigo_establecimiento, invoice.codigo_punto_emision),
        int(nuevo) + 1,
        invoice.tipo_comprobante or "FACTURA",
    )
    db.commit()
    db.refresh(invoice)
    log_activity(
        db,
        "FACTURA_RENUMERADA",
        f"Factura #{invoice.id}: {anterior} → {invoice.numero_comprobante}",
    )
    return invoice


def _emission_point_id(db: Session, codigo_establecimiento: str, codigo_punto_emision: str) -> int:
    from app.models.sri_establishment import SriEstablishment
    from app.models.sri_emission_point import SriEmissionPoint

    est = db.query(SriEstablishment).filter(SriEstablishment.codigo == codigo_establecimiento).first()
    if not est:
        raise ValueError(f"Establecimiento {codigo_establecimiento} no configurado.")
    pto = (
        db.query(SriEmissionPoint)
        .filter(
            SriEmissionPoint.establishment_id == est.id,
            SriEmissionPoint.codigo == codigo_punto_emision,
        )
        .first()
    )
    if not pto:
        raise ValueError(f"Punto de emisión {codigo_punto_emision} no configurado.")
    return pto.id
