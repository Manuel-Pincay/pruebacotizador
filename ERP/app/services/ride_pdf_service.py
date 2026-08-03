import io
import json
from collections import defaultdict

from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.utils.image_storage import resolve_logo_path
from app.utils.sri_constants import label_forma_pago

# Paleta gris para el RIDE (formal pero con contraste visual)
GRAY_BORDER = colors.HexColor("#6b7280")
GRAY_LINE = colors.HexColor("#d1d5db")
GRAY_HEADER = colors.HexColor("#e5e7eb")
GRAY_HEADER_DARK = colors.HexColor("#d1d5db")
GRAY_SECTION = colors.HexColor("#f3f4f6")
GRAY_ZEBRA = colors.HexColor("#f9fafb")
GRAY_TOTAL = colors.HexColor("#e5e7eb")
GRAY_TITLE_TEXT = colors.HexColor("#374151")

_base = getSampleStyleSheet()
ride_styles = StyleSheet1()
ride_styles.add(ParagraphStyle(name="RideSmall", parent=_base["Normal"], fontSize=7, leading=9))
ride_styles.add(ParagraphStyle(name="RideSmallBold", parent=ride_styles["RideSmall"], fontName="Helvetica-Bold"))
ride_styles.add(
    ParagraphStyle(
        name="RideTitle",
        parent=_base["Normal"],
        fontSize=12,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        textColor=GRAY_TITLE_TEXT,
    )
)


def _money(value) -> str:
    return f"${float(value or 0):.2f}"


def _resolve_logo_path(config: CompanyConfig | None, logo_path: str | None) -> str | None:
    if logo_path:
        resolved = resolve_logo_path(logo_path)
        if resolved:
            return resolved
    if not config:
        return None
    for candidate in (config.logo, config.company_icon):
        resolved = resolve_logo_path(candidate)
        if resolved:
            return resolved
    return None


def _logo_flowable(logo_file: str, max_w: float, max_h: float):
    try:
        return Image(logo_file, width=max_w, height=max_h, kind="proportional")
    except Exception:
        return None


def _para(text: str, style, align=TA_LEFT):
    raw = text or ""
    if "<" in raw and ">" in raw:
        safe = raw
    else:
        safe = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, ParagraphStyle(name="", parent=style, alignment=align))


def _border_style(*, header_rows=None, total_row=None, label_col_gray=False):
    """Estilos comunes: bordes grises, cabeceras y filas alternas."""
    style = [
        ("BOX", (0, 0), (-1, -1), 0.8, GRAY_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, GRAY_LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for row in header_rows or []:
        style.append(("BACKGROUND", (0, row), (-1, row), GRAY_SECTION))
        style.append(("FONTNAME", (0, row), (-1, row), "Helvetica-Bold"))
    if label_col_gray:
        style.append(("BACKGROUND", (0, 0), (0, -1), GRAY_ZEBRA))
    if total_row is not None:
        style.append(("BACKGROUND", (0, total_row), (-1, total_row), GRAY_TOTAL))
        style.append(("FONTNAME", (0, total_row), (-1, total_row), "Helvetica-Bold"))
    return style


def _apply_zebra(table: Table, start_row: int, end_row: int | None = None):
    """Filas impares con fondo gris muy claro."""
    if end_row is None:
        end_row = table._cellvalues and len(table._cellvalues) - 1 or start_row
    commands = []
    for row in range(start_row, end_row + 1):
        if row % 2 == 0:
            commands.append(("BACKGROUND", (0, row), (-1, row), GRAY_ZEBRA))
    if commands:
        table.setStyle(TableStyle(commands))


def _fit_barcode(clave: str, max_width: float, bar_height: float = 10 * mm):
    """Código de barras Code128 dimensionado para no desbordar el ancho disponible."""
    clave = (clave or "").strip() or "0"
    # Code128 ≈ 11 módulos por carácter + quiet zones / start-stop
    modules = max(len(clave) * 11 + 55, 80)
    bar_width = max(0.11 * mm, min(0.28 * mm, max_width / modules))
    drawing = createBarcodeDrawing(
        "Code128",
        value=clave,
        barHeight=bar_height,
        barWidth=bar_width,
        humanReadable=0,
    )
    # Ajuste fino si aún se pasa (fuentes/quiet zones reales)
    if getattr(drawing, "width", 0) and drawing.width > max_width:
        factor = max_width / float(drawing.width)
        bar_width = max(0.10 * mm, bar_width * factor * 0.98)
        drawing = createBarcodeDrawing(
            "Code128",
            value=clave,
            barHeight=bar_height,
            barWidth=bar_width,
            humanReadable=0,
        )
    return drawing


def _col_widths(total: float, fractions: list[float]) -> list[float]:
    """Fracciones que suman 1 → anchos exactos que suman `total`."""
    s = sum(fractions) or 1.0
    widths = [total * (f / s) for f in fractions]
    # Corregir redondeo en la última columna
    widths[-1] = total - sum(widths[:-1])
    return widths


def generate_ride_pdf(
    invoice: ElectronicInvoice,
    config: CompanyConfig | None,
    *,
    dir_sucursal: str | None = None,
    logo_path: str | None = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )
    story = []
    # Ancho único para TODAS las secciones (alineación vertical de bordes)
    content_w = A4[0] - 20 * mm
    half = content_w / 2
    gap = 2 * mm
    left_w = (content_w - gap) / 2
    right_w = content_w - gap - left_w

    company = (config.sri_razon_social if config else None) or (config.company_name if config else "Empresa")
    nombre_comercial = (config.sri_nombre_comercial if config else None) or company
    ruc = (config.sri_ruc if config else None) or ""
    dir_matriz = (config.sri_direccion_matriz if config else None) or ""
    dir_branch = dir_sucursal or dir_matriz
    contrib_especial = (config.sri_contribuyente_especial if config else None) or ""
    obligado = "SI" if config and config.sri_obligado_contabilidad else "NO"
    rimpe = (config.sri_contribuyente_rimpe if config else None) or ""
    ambiente = (config.sri_ambiente if config else "PRUEBAS") or "PRUEBAS"
    ambiente_label = "PRODUCCIÓN" if ambiente == "PRODUCCION" else "PRUEBAS"
    tipo_emision = (config.sri_tipo_emision if config else "NORMAL") or "NORMAL"

    logo_file = _resolve_logo_path(config, logo_path)
    company_lines = [[_para(f"<b>{company}</b>", ride_styles["RideSmall"])]]
    if nombre_comercial and nombre_comercial != company:
        company_lines.append([_para(nombre_comercial, ride_styles["RideSmall"])])
    company_lines.extend(
        [
            [_para(f"<b>Dir. Matriz:</b> {dir_matriz}", ride_styles["RideSmall"])],
            [_para(f"<b>Dir. Sucursal:</b> {dir_branch}", ride_styles["RideSmall"])],
            [_para(f"<b>Contribuyente Especial Nro:</b> {contrib_especial or '00000'}", ride_styles["RideSmall"])],
            [_para(f"<b>OBLIGADO A LLEVAR CONTABILIDAD:</b> {obligado}", ride_styles["RideSmall"])],
        ]
    )
    if rimpe:
        company_lines.append([_para(rimpe, ride_styles["RideSmall"])])

    logo_col_w = 36 * mm
    text_col_w = left_w - logo_col_w - 2 * mm
    logo_img = _logo_flowable(logo_file, logo_col_w - 4 * mm, 20 * mm) if logo_file else None
    if logo_img:
        logo_block = Table([[logo_img]], colWidths=[logo_col_w])
        logo_block.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("BACKGROUND", (0, 0), (-1, -1), GRAY_ZEBRA),
                ]
            )
        )
        text_block = Table(company_lines, colWidths=[text_col_w])
        text_block.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        header_left_inner = Table(
            [[logo_block, text_block]],
            colWidths=[logo_col_w, text_col_w],
        )
        header_left_inner.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        left_box = Table([[header_left_inner]], colWidths=[left_w])
    else:
        left_box = Table(company_lines, colWidths=[left_w])

    auth_num = invoice.numero_autorizacion or invoice.clave_acceso or ""
    auth_dt = ""
    if invoice.fecha_autorizacion:
        auth_dt = invoice.fecha_autorizacion.strftime("%Y-%m-%d %H:%M:%S-05:00")
    elif invoice.fecha_emision:
        auth_dt = invoice.fecha_emision.strftime("%Y-%m-%d %H:%M:%S-05:00")

    clave = invoice.clave_acceso or ""
    barcode = _fit_barcode(clave, max_width=right_w - 8 * mm, bar_height=10 * mm)

    right_rows = [
        [_para(f"<b>R.U.C.:</b> {ruc}", ride_styles["RideSmall"])],
        [_para("<b>FACTURA</b>", ride_styles["RideTitle"])],
        [_para(f"<b>No.</b> {invoice.numero_comprobante}", ride_styles["RideSmallBold"], TA_CENTER)],
        [_para("<b>NÚMERO DE AUTORIZACIÓN</b>", ride_styles["RideSmallBold"], TA_CENTER)],
        [_para(auth_num, ride_styles["RideSmall"], TA_CENTER)],
        [_para(auth_dt, ride_styles["RideSmall"], TA_CENTER)],
        [_para(f"<b>AMBIENTE:</b> {ambiente_label}", ride_styles["RideSmall"])],
        [_para(f"<b>EMISIÓN:</b> {tipo_emision}", ride_styles["RideSmall"])],
        [_para("<b>CLAVE DE ACCESO</b>", ride_styles["RideSmallBold"], TA_CENTER)],
        [_para(clave, ride_styles["RideSmall"], TA_CENTER)],
        [barcode],
    ]
    right_box = Table(right_rows, colWidths=[right_w])
    right_style = _border_style()
    right_style.extend(
        [
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, 0), GRAY_SECTION),
            ("BACKGROUND", (0, 1), (-1, 1), GRAY_HEADER_DARK),
            # Celda del barcode centrada y sin exceder
            ("ALIGN", (0, -1), (0, -1), "CENTER"),
            ("LEFTPADDING", (0, -1), (0, -1), 2),
            ("RIGHTPADDING", (0, -1), (0, -1), 2),
        ]
    )
    right_box.setStyle(TableStyle(right_style))

    left_style = _border_style()
    left_style.append(("BACKGROUND", (0, 0), (-1, -1), colors.white))
    left_box.setStyle(TableStyle(left_style))

    # Gap visual entre cajas sin romper el ancho total
    header = Table(
        [[left_box, "", right_box]],
        colWidths=[left_w, gap, right_w],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 3 * mm))

    client_name = ""
    client_id = ""
    if invoice.client:
        client_name = (invoice.client.company or invoice.client.name or "").strip()
        client_id = (invoice.client.ruc_ci or "").strip()
    fecha_emision = invoice.fecha_emision.strftime("%d/%m/%Y") if invoice.fecha_emision else ""

    cust_cols = _col_widths(content_w, [0.62, 0.38])
    customer_rows = [
        [
            _para(f"<b>Razón Social / Nombres y Apellidos:</b> {client_name}", ride_styles["RideSmall"]),
            _para(f"<b>Identificación:</b> {client_id}", ride_styles["RideSmall"]),
        ],
        [
            _para(f"<b>Fecha Emisión:</b> {fecha_emision}", ride_styles["RideSmall"]),
            _para("<b>Guía Remisión:</b>", ride_styles["RideSmall"]),
        ],
    ]
    customer = Table(customer_rows, colWidths=cust_cols)
    cust_style = _border_style()
    cust_style.append(("BACKGROUND", (0, 0), (-1, 0), GRAY_SECTION))
    customer.setStyle(TableStyle(cust_style))
    story.append(customer)
    story.append(Spacer(1, 2 * mm))

    detail_header = [
        "Cod.\nPrincipal",
        "Cant.",
        "Descripción",
        "Detalle\nAdicional",
        "Unidad\nMedida",
        "Precio\nUnitario",
        "Descuento",
        "Precio\nTotal",
    ]
    detail_rows = [[_para(h, ride_styles["RideSmallBold"], TA_CENTER) for h in detail_header]]
    for line in invoice.lines:
        line_total = float(line.precio_total_sin_impuesto or 0) + float(line.valor_iva or 0)
        detail_rows.append(
            [
                _para(line.codigo_principal or "", ride_styles["RideSmall"], TA_CENTER),
                _para(f"{float(line.cantidad or 0):.2f}", ride_styles["RideSmall"], TA_CENTER),
                _para(line.descripcion or "", ride_styles["RideSmall"]),
                _para("", ride_styles["RideSmall"]),
                _para("UN", ride_styles["RideSmall"], TA_CENTER),
                _para(_money(line.precio_unitario), ride_styles["RideSmall"], TA_RIGHT),
                _para(_money(line.descuento), ride_styles["RideSmall"], TA_RIGHT),
                _para(_money(line_total), ride_styles["RideSmall"], TA_RIGHT),
            ]
        )
    detail_cols = _col_widths(content_w, [0.11, 0.07, 0.28, 0.12, 0.08, 0.11, 0.10, 0.13])
    detail_table = Table(detail_rows, colWidths=detail_cols, repeatRows=1)
    det_style = _border_style(header_rows=[0])
    det_style.extend(
        [
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
            ("ALIGN", (5, 1), (-1, -1), "RIGHT"),
        ]
    )
    detail_table.setStyle(TableStyle(det_style))
    if len(detail_rows) > 2:
        _apply_zebra(detail_table, 1, len(detail_rows) - 1)
    story.append(detail_table)
    story.append(Spacer(1, 2 * mm))

    subtotals_by_tarifa = defaultdict(float)
    iva_by_tarifa = defaultdict(float)
    subtotal_no_objeto = 0.0
    for line in invoice.lines:
        tarifa = float(line.tarifa_iva or 0)
        base = float(line.precio_total_sin_impuesto or 0)
        iva_by_tarifa[tarifa] += float(line.valor_iva or 0)
        if tarifa > 0:
            subtotals_by_tarifa[tarifa] += base
        elif line.codigo_iva == "6":
            subtotal_no_objeto += base
        else:
            subtotals_by_tarifa[0] += base

    totals_rows = []
    for tarifa in sorted(subtotals_by_tarifa.keys(), reverse=True):
        if tarifa > 0:
            totals_rows.append([f"SubTotal {tarifa:g}%", _money(subtotals_by_tarifa[tarifa])])
        else:
            totals_rows.append(["SubTotal 0%", _money(subtotals_by_tarifa[tarifa])])
    if subtotal_no_objeto > 0:
        totals_rows.append(["SubTotal No Objeto IVA", _money(subtotal_no_objeto)])
    totals_rows.extend(
        [
            ["SubTotal Sin Impuestos", _money(invoice.subtotal_sin_impuestos)],
            ["Descuento", _money(invoice.descuento)],
            ["ICE", _money(0)],
        ]
    )
    for tarifa in sorted(iva_by_tarifa.keys(), reverse=True):
        if tarifa > 0 and iva_by_tarifa[tarifa] > 0:
            totals_rows.append([f"IVA {tarifa:g}%", _money(iva_by_tarifa[tarifa])])
    totals_rows.extend(
        [
            ["Propina", _money(invoice.propina)],
            ["VALOR TOTAL", _money(invoice.importe_total)],
        ]
    )

    info_fields = []
    try:
        info_fields = json.loads(invoice.info_adicional_json) if invoice.info_adicional_json else []
    except json.JSONDecodeError:
        info_fields = []
    if invoice.client:
        if invoice.client.phone and not any(f.get("nombre") == "Telefono" for f in info_fields):
            info_fields.insert(0, {"nombre": "Telefono", "valor": invoice.client.phone})
        if invoice.client.address and not any(f.get("nombre") == "Direccion" for f in info_fields):
            info_fields.insert(0, {"nombre": "Direccion", "valor": invoice.client.address})
        if invoice.client.email and not any(f.get("nombre") == "Email" for f in info_fields):
            info_fields.insert(0, {"nombre": "Email", "valor": invoice.client.email})

    info_lines = [[_para("<b>Información Adicional</b>", ride_styles["RideSmallBold"])]]
    for field in info_fields:
        info_lines.append(
            [_para(f"<b>{field.get('nombre', '')}:</b> {field.get('valor', '')}", ride_styles["RideSmall"])]
        )
    info_lines.append(
        [
            _para(
                "<b>Nota:</b> Si su pago es mediante transferencia bancaria, envíe el comprobante al correo indicado.",
                ride_styles["RideSmall"],
            )
        ]
    )

    # Bloque inferior: un solo marco externo para igualar alturas y bordes
    info_w, totals_w = _col_widths(content_w, [0.58, 0.42])
    label_w, value_w = _col_widths(totals_w, [0.55, 0.45])

    info_inner = Table(info_lines, colWidths=[info_w])
    info_inner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GRAY_HEADER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    totals_data = [
        [_para(f"<b>{label}</b>", ride_styles["RideSmall"]), _para(str(val), ride_styles["RideSmall"], TA_RIGHT)]
        for label, val in totals_rows
    ]
    totals_inner = Table(totals_data, colWidths=[label_w, value_w])
    total_row_idx = len(totals_data) - 1
    tot_style = [
        ("INNERGRID", (0, 0), (-1, -1), 0.35, GRAY_LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (0, -1), GRAY_ZEBRA),
        ("BACKGROUND", (0, total_row_idx), (-1, total_row_idx), GRAY_TOTAL),
        ("FONTNAME", (0, total_row_idx), (-1, total_row_idx), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]
    totals_inner.setStyle(TableStyle(tot_style))

    bottom = Table([[info_inner, totals_inner]], colWidths=[info_w, totals_w])
    bottom.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, GRAY_BORDER),
                ("LINEBEFORE", (1, 0), (1, -1), 0.8, GRAY_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(bottom)
    story.append(Spacer(1, 2 * mm))

    pagos = []
    try:
        pagos = json.loads(invoice.pagos_json) if invoice.pagos_json else []
    except json.JSONDecodeError:
        pagos = []
    pay_header = [
        _para("<b>Forma de Pago</b>", ride_styles["RideSmallBold"]),
        _para("<b>Valor</b>", ride_styles["RideSmallBold"], TA_RIGHT),
        _para("<b>Plazo</b>", ride_styles["RideSmallBold"], TA_CENTER),
        _para("<b>Tiempo</b>", ride_styles["RideSmallBold"], TA_CENTER),
    ]
    pay_rows = [pay_header]
    for pago in pagos:
        codigo = str(pago.get("forma_pago") or pago.get("formaPago") or "01")
        pay_rows.append(
            [
                _para(label_forma_pago(codigo), ride_styles["RideSmall"]),
                _para(_money(pago.get("total")), ride_styles["RideSmall"], TA_RIGHT),
                _para(str(pago.get("plazo") or "0"), ride_styles["RideSmall"], TA_CENTER),
                _para(str(pago.get("unidad_tiempo") or "Dias"), ride_styles["RideSmall"], TA_CENTER),
            ]
        )
    if not pagos:
        pay_rows.append(
            [
                _para("Sin utilización del sistema financiero (Efectivo)", ride_styles["RideSmall"]),
                _para(_money(invoice.importe_total), ride_styles["RideSmall"], TA_RIGHT),
                _para("0", ride_styles["RideSmall"], TA_CENTER),
                _para("Dias", ride_styles["RideSmall"], TA_CENTER),
            ]
        )
    pay_cols = _col_widths(content_w, [0.50, 0.20, 0.15, 0.15])
    pay_table = Table(pay_rows, colWidths=pay_cols)
    pay_style = _border_style(header_rows=[0])
    pay_table.setStyle(TableStyle(pay_style))
    if len(pay_rows) > 2:
        _apply_zebra(pay_table, 1, len(pay_rows) - 1)
    story.append(pay_table)

    if invoice.estado == "AUTORIZADA" and invoice.fecha_autorizacion:
        story.append(Spacer(1, 2 * mm))
        auth_banner = Table(
            [[_para(
                f"Documento autorizado por el SRI el {invoice.fecha_autorizacion.strftime('%d/%m/%Y %H:%M')}",
                ride_styles["RideSmallBold"],
                TA_CENTER,
            )]],
            colWidths=[content_w],
        )
        auth_banner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), GRAY_SECTION),
                    ("BOX", (0, 0), (-1, -1), 0.5, GRAY_LINE),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(auth_banner)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
