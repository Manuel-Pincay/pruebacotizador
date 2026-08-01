import json
import re
from dataclasses import dataclass, field

from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.models.sri_certificate import SriCertificate
from app.utils.clave_acceso import ambiente_desde_clave
from app.models.sri_emission_point import SriEmissionPoint
from app.models.sri_establishment import SriEstablishment
from app.utils.sri_constants import CONSUMIDOR_FINAL


@dataclass
class ValidationIssue:
    campo: str
    mensaje: str


@dataclass
class ValidationResult:
    valido: bool = True
    errores: list = field(default_factory=list)
    advertencias: list = field(default_factory=list)


def _email_ok(value: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (value or "").strip()))


def validate_sri_form_input(
    *,
    sri_ruc: str,
    sri_razon_social: str,
    sri_direccion_matriz: str,
    sri_email_notificacion: str,
    sri_default_establishment: str,
    sri_default_emission_point: str,
    certificate_uploaded: bool,
    certificate_password: str,
    has_existing_certificate: bool,
) -> ValidationResult:
    """Validación al guardar el formulario único de configuración SRI."""
    result = ValidationResult()
    ruc = (sri_ruc or "").strip()
    if not re.match(r"^\d{13}$", ruc):
        result.errores.append(ValidationIssue("sri.ruc", "El RUC debe tener exactamente 13 dígitos."))
    if not (sri_razon_social or "").strip():
        result.errores.append(ValidationIssue("sri.razon_social", "La razón social es obligatoria."))
    if not (sri_direccion_matriz or "").strip():
        result.errores.append(ValidationIssue("sri.direccion_matriz", "La dirección matriz es obligatoria."))
    email = (sri_email_notificacion or "").strip()
    if not email:
        result.errores.append(ValidationIssue("sri.email", "El email de notificación es obligatorio."))
    elif not _email_ok(email):
        result.errores.append(ValidationIssue("sri.email", "El email de notificación no es válido."))
    estab = (sri_default_establishment or "").strip().zfill(3)[-3:]
    pto = (sri_default_emission_point or "").strip().zfill(3)[-3:]
    if not re.match(r"^\d{3}$", estab):
        result.errores.append(ValidationIssue("sri.establecimiento", "Establecimiento: 3 dígitos (ej. 001)."))
    if not re.match(r"^\d{3}$", pto):
        result.errores.append(ValidationIssue("sri.punto_emision", "Punto de emisión: 3 dígitos (ej. 001)."))
    if certificate_uploaded and not (certificate_password or "").strip():
        result.errores.append(
            ValidationIssue("sri.certificado", "Ingrese la contraseña del certificado .p12.")
        )
    if not has_existing_certificate and not certificate_uploaded:
        result.advertencias.append(
            ValidationIssue("sri.certificado", "Aún no ha subido el certificado .p12 (requerido para emitir).")
        )
    result.valido = len(result.errores) == 0
    return result


def validate_sri_config(db, config: CompanyConfig, certificate: SriCertificate | None) -> ValidationResult:
    result = ValidationResult()
    if not config:
        result.errores.append(ValidationIssue("sri.config", "Configure la empresa emisora SRI antes de emitir."))
        result.valido = False
        return result
    if not config.sri_active:
        result.errores.append(ValidationIssue("sri.active", "La facturación electrónica SRI no está activada."))
    if not config.sri_ruc or not re.match(r"^\d{13}$", config.sri_ruc.strip()):
        result.errores.append(ValidationIssue("sri.ruc", "Configure el RUC de la empresa (13 dígitos)."))
    if not (config.sri_razon_social or "").strip():
        result.errores.append(ValidationIssue("sri.razon_social", "Configure la razón social fiscal."))
    if not (config.sri_direccion_matriz or "").strip():
        result.errores.append(ValidationIssue("sri.direccion_matriz", "Configure la dirección matriz."))
    if config.sri_ambiente not in ("PRUEBAS", "PRODUCCION"):
        result.errores.append(ValidationIssue("sri.ambiente", "Configure el ambiente SRI (PRUEBAS o PRODUCCION)."))
    if not certificate:
        result.errores.append(ValidationIssue("sri.certificado", "Configure el certificado electrónico (.p12)."))
    elif certificate.valid_to and certificate.valid_to < __import__("datetime").datetime.utcnow():
        result.errores.append(ValidationIssue("sri.certificado", "El certificado digital está vencido."))
    if not config.sri_default_establishment:
        result.errores.append(ValidationIssue("sri.establecimiento", "Configure el establecimiento por defecto."))
    if not config.sri_default_emission_point:
        result.errores.append(ValidationIssue("sri.punto_emision", "Configure el punto de emisión por defecto."))
    else:
        est = (
            db.query(SriEstablishment)
            .filter(SriEstablishment.codigo == config.sri_default_establishment)
            .first()
        )
        if not est:
            result.errores.append(
                ValidationIssue("sri.establecimiento", f"Establecimiento {config.sri_default_establishment} no existe.")
            )
        else:
            pto = (
                db.query(SriEmissionPoint)
                .filter(
                    SriEmissionPoint.establishment_id == est.id,
                    SriEmissionPoint.codigo == config.sri_default_emission_point,
                )
                .first()
            )
            if not pto:
                result.errores.append(
                    ValidationIssue(
                        "sri.punto_emision",
                        f"Punto de emisión {config.sri_default_emission_point} no configurado.",
                    )
                )
    result.valido = len(result.errores) == 0
    return result


def validate_client_for_invoice(client: Client) -> ValidationResult:
    result = ValidationResult()
    razon = (client.company or client.name or "").strip()
    if not razon:
        result.errores.append(ValidationIssue("cliente.razon_social", "El cliente debe tener nombre o empresa."))
    ident = (client.ruc_ci or "").strip()
    tipo = (client.tipo_identificacion or "CEDULA").upper()
    if not ident:
        result.errores.append(ValidationIssue("cliente.identificacion", "El cliente debe tener RUC/cédula."))
    elif tipo == "RUC" and not re.match(r"^\d{13}$", ident):
        result.errores.append(ValidationIssue("cliente.identificacion", "El RUC del cliente debe tener 13 dígitos."))
    elif tipo == "CEDULA" and not re.match(r"^\d{10}$", ident):
        result.errores.append(ValidationIssue("cliente.identificacion", "La cédula del cliente debe tener 10 dígitos."))
    elif tipo == "CONSUMIDOR_FINAL" and ident != CONSUMIDOR_FINAL:
        result.advertencias.append(
            ValidationIssue(
                "cliente.identificacion",
                "Consumidor final debería usar identificación 9999999999999",
            )
        )
    if not (client.email or "").strip():
        result.errores.append(ValidationIssue("cliente.email", "El correo del cliente es obligatorio para facturar."))
    elif not _email_ok(client.email):
        result.errores.append(ValidationIssue("cliente.email", "El correo del cliente no es válido."))
    result.valido = len(result.errores) == 0
    return result


def _round2(value) -> float:
    return round(float(value or 0), 2)


def _validate_pagos(invoice: ElectronicInvoice, result: ValidationResult):
    try:
        pagos = json.loads(invoice.pagos_json) if invoice.pagos_json else []
    except json.JSONDecodeError:
        pagos = []
    if not pagos:
        result.errores.append(ValidationIssue("factura.pagos", "Debe registrar al menos una forma de pago."))
        return
    sum_pagos = 0.0
    for i, raw in enumerate(pagos):
        forma = str(raw.get("forma_pago") or raw.get("formaPago") or "")
        total = float(raw.get("total") or 0)
        if not re.match(r"^\d{2}$", forma):
            result.errores.append(
                ValidationIssue(f"pagos[{i}].forma_pago", "Forma de pago inválida (código Tabla 24 SRI).")
            )
        if total <= 0:
            result.errores.append(
                ValidationIssue(f"pagos[{i}].total", "El valor de la forma de pago debe ser mayor a cero.")
            )
        plazo = raw.get("plazo")
        unidad = raw.get("unidad_tiempo")
        if plazo not in (None, "") and not unidad:
            result.errores.append(
                ValidationIssue(f"pagos[{i}].unidad_tiempo", "Si indica plazo, debe especificar la unidad de tiempo.")
            )
        sum_pagos += total
    sum_pagos = _round2(sum_pagos)
    importe = _round2(invoice.importe_total)
    if abs(sum_pagos - importe) > 0.01:
        result.errores.append(
            ValidationIssue(
                "factura.pagos",
                f"La suma de pagos (${sum_pagos:.2f}) debe igualar el total (${importe:.2f}).",
            )
        )


def _validate_totales(invoice: ElectronicInvoice, result: ValidationResult):
    if not invoice.lines:
        return
    sum_det = _round2(sum(float(l.precio_total_sin_impuesto or 0) for l in invoice.lines))
    sum_iva = _round2(sum(float(l.valor_iva or 0) for l in invoice.lines))
    subtotal = _round2(invoice.subtotal_sin_impuestos)
    iva = _round2(invoice.subtotal_iva)
    descuento = _round2(invoice.descuento)
    propina = _round2(invoice.propina)
    total = _round2(invoice.importe_total)
    esperado = _round2(subtotal + iva - descuento + propina)
    if abs(sum_det - subtotal) > 0.02:
        result.errores.append(
            ValidationIssue(
                "factura.subtotal_sin_impuestos",
                f"Subtotal sin impuestos (${subtotal:.2f}) no coincide con la suma de detalles (${sum_det:.2f}).",
            )
        )
    if abs(sum_iva - iva) > 0.02:
        result.errores.append(
            ValidationIssue(
                "factura.subtotal_iva",
                f"IVA (${iva:.2f}) no coincide con la suma de detalles (${sum_iva:.2f}).",
            )
        )
    if abs(esperado - total) > 0.02:
        result.errores.append(
            ValidationIssue(
                "factura.importe_total",
                f"Total (${total:.2f}) no cuadra con subtotal + IVA - descuento + propina (${esperado:.2f}).",
            )
        )


def _validate_invoice_establishment(db, invoice: ElectronicInvoice, result: ValidationResult):
    """Como FactuSRI comprobante-emision.validator validarEstablecimiento."""
    est = (
        db.query(SriEstablishment)
        .filter(SriEstablishment.codigo == invoice.codigo_establecimiento)
        .first()
    )
    if not est:
        result.errores.append(
            ValidationIssue(
                "factura.establecimiento",
                f"Establecimiento {invoice.codigo_establecimiento} no configurado.",
            )
        )
        return
    if not (est.direccion or "").strip():
        result.errores.append(
            ValidationIssue("factura.establecimiento", "El establecimiento debe tener dirección registrada.")
        )
    pto = (
        db.query(SriEmissionPoint)
        .filter(
            SriEmissionPoint.establishment_id == est.id,
            SriEmissionPoint.codigo == invoice.codigo_punto_emision,
        )
        .first()
    )
    if not pto:
        result.errores.append(
            ValidationIssue(
                "factura.punto_emision",
                f"Punto de emisión {invoice.codigo_punto_emision} no configurado.",
            )
        )


def _validate_info_adicional(invoice: ElectronicInvoice, result: ValidationResult):
    try:
        campos = json.loads(invoice.info_adicional_json) if invoice.info_adicional_json else []
    except json.JSONDecodeError:
        campos = []
    for i, campo in enumerate(campos):
        nombre = (campo.get("nombre") or "").strip()
        valor = (campo.get("valor") or "").strip()
        if len(valor) > 300:
            result.errores.append(
                ValidationIssue(
                    f"infoAdicional[{i}]",
                    f"El valor del campo '{nombre}' supera 300 caracteres.",
                )
            )


def validate_invoice_for_emission(db, invoice: ElectronicInvoice, config: CompanyConfig, certificate) -> ValidationResult:
    result = validate_sri_config(db, config, certificate)
    _validate_invoice_establishment(db, invoice, result)
    if invoice.client:
        client_result = validate_client_for_invoice(invoice.client)
        result.errores.extend(client_result.errores)
        result.advertencias.extend(client_result.advertencias)
    if invoice.estado not in ("BORRADOR", "RECHAZADA", "ERROR", "PENDIENTE_ENVIO"):
        result.errores.append(
            ValidationIssue("factura.estado", f"No se puede emitir una factura en estado {invoice.estado}.")
        )
    if not re.match(r"^\d{49}$", invoice.clave_acceso or ""):
        result.errores.append(ValidationIssue("factura.clave_acceso", "Clave de acceso inválida."))
    if not re.match(r"^\d{9}$", invoice.secuencial or ""):
        result.errores.append(ValidationIssue("factura.secuencial", "Secuencial inválido."))
    if float(invoice.importe_total or 0) <= 0:
        result.errores.append(ValidationIssue("factura.importe_total", "El total debe ser mayor a cero."))
    if not invoice.lines:
        result.errores.append(ValidationIssue("factura.detalles", "La factura debe tener al menos un detalle."))
    if (invoice.tipo_comprobante or "FACTURA").upper() == "NOTA_CREDITO":
        if not (invoice.motivo or "").strip():
            result.errores.append(ValidationIssue("nota_credito.motivo", "Motivo de la nota de crédito obligatorio."))
        if not (invoice.num_doc_modificado or "").strip():
            result.errores.append(ValidationIssue("nota_credito.doc_modificado", "Documento modificado obligatorio."))
        if not invoice.fecha_emision_doc_sustento:
            result.errores.append(
                ValidationIssue("nota_credito.fecha_sustento", "Fecha del documento sustento obligatoria.")
            )
    expected_amb = (config.sri_ambiente or "PRUEBAS").upper()
    clave_amb = ambiente_desde_clave(invoice.clave_acceso)
    if clave_amb and clave_amb != expected_amb:
        result.advertencias.append(
            ValidationIssue(
                "factura.clave_acceso",
                f"La clave fue generada en {clave_amb} pero la configuración está en {expected_amb}. "
                "Se regenerará automáticamente al emitir.",
            )
        )
    if expected_amb == "PRODUCCION" and not (config.sri_contribuyente_rimpe or "").strip():
        if not (config.sri_contribuyente_especial or "").strip():
            result.advertencias.append(
                ValidationIssue(
                    "sri.contribuyente_rimpe",
                    "En PRODUCCIÓN, si es contribuyente RIMPE debe indicar el texto exacto del SRI "
                    "(ej. CONTRIBUYENTE NEGOCIO POPULAR - RÉGIMEN RIMPE).",
                )
            )
    for i, line in enumerate(invoice.lines):
        prefix = f"detalles[{i}]"
        if not (line.codigo_principal or "").strip():
            result.errores.append(ValidationIssue(f"{prefix}.codigo", "Código principal obligatorio."))
        if not (line.descripcion or "").strip():
            result.errores.append(ValidationIssue(f"{prefix}.descripcion", "Descripción obligatoria."))
        if float(line.cantidad or 0) <= 0:
            result.errores.append(ValidationIssue(f"{prefix}.cantidad", "Cantidad inválida."))
    _validate_totales(invoice, result)
    if (invoice.tipo_comprobante or "FACTURA").upper() != "NOTA_CREDITO":
        _validate_pagos(invoice, result)
    _validate_info_adicional(invoice, result)
    result.valido = len(result.errores) == 0
    return result


def format_validation_errors(result: ValidationResult) -> str:
    if result.valido:
        return ""
    return "\n".join(f"• {e.mensaje}" for e in result.errores)


def issues_to_json(result: ValidationResult) -> str:
    return json.dumps(
        {
            "errores": [{"campo": e.campo, "mensaje": e.mensaje} for e in result.errores],
            "advertencias": [{"campo": a.campo, "mensaje": a.mensaje} for a in result.advertencias],
        },
        ensure_ascii=False,
    )
