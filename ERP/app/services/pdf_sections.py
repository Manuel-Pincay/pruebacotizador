from reportlab.platypus import Table, TableStyle, Paragraph, Image, Spacer

from app.services.logo_types import logo_type_pdf_label, resolve_item_logo_type
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4

from reportlab.platypus.flowables import HRFlowable

import os

from app.utils.image_storage import quotation_item_image_path


def build_header(quotation, config, styles):

    created = quotation.created_at.strftime("%d/%m/%Y")

    entrega = (
        quotation.delivery_date.strftime("%d/%m/%Y") if quotation.delivery_date else "-"
    )

    estado = quotation.status or "Pendiente"

    logo_path = None

    if config.logo:

        for candidate in (
            os.path.join("uploads", "logos", config.logo),
            os.path.join("uploads", config.logo),
            config.logo,
        ):
            if os.path.exists(candidate):
                logo_path = candidate
                break

    if not logo_path:

        logo_path = "app/static/logo.png"

    company_name = config.company_name or "SISTEMA ERP"

    logo_elements = []

    if os.path.exists(logo_path):

        logo_elements.append(Image(logo_path, width=90, height=70))

    logo_elements.append(
        Paragraph(
            f"""
            <para align="center">
            <font size="12">
            <b>{company_name}</b>
            </font>
            <br/>
            <font size="7"
            color="{config.primary_color}">
            DISEÑO • IMPRESIÓN LASER • PUBLICIDAD
            </font>
            </para>
            """,
            styles["Normal"],
        )
    )

    logo_column = Table([[item] for item in logo_elements])

    title_column = Table(
        [
            [
                Paragraph(
                    """
                    <para align="center">
                    <font size="16">
                    <b>COTIZACIÓN</b>
                    </font>
                    </para>
                    """,
                    styles["Normal"],
                )
            ],
            [
                Paragraph(
                    f"""
                    <para align="center">
                    <font size="18">
                    <font color="{config.primary_color}">
                    <b>#{quotation.id}</b>
                    </font>
                    </font>
                    </para>
                    """,
                    styles["Normal"],
                )
            ],
        ]
    )

    info_column = Paragraph(
        f"""
        <font size="10">

        Fecha emisión:
        <b>{created}</b>

        <br/><br/>

        Fecha entrega:
        <b>{entrega}</b>

        <br/><br/>

        Estado:
        <font color="{config.primary_color}">
        <b>{estado.upper()}</b>
        </font>

        </font>
        """,
        styles["Normal"],
    )

    header = Table(
        [[logo_column, title_column, info_column]], colWidths=[180, 180, 180]
    )

    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    return header


def build_client_section(quotation, config, styles):

    client = quotation.client
    phone = (client.phone or "-").replace("&", "&amp;")
    address = (client.address or "-").replace("&", "&amp;")
    name = (client.name or "-").replace("&", "&amp;")
    ruc_ci = (getattr(client, "ruc_ci", None) or "-").replace("&", "&amp;")

    label_style = ParagraphStyle(
        "ClientFieldLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#6B7280"),
        alignment=TA_LEFT,
    )
    value_style = ParagraphStyle(
        "ClientFieldValue",
        parent=styles["Normal"],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#374151"),
        alignment=TA_LEFT,
    )

    label_w = 42
    value_w = (530 - label_w * 2) // 2

    def _row(field_label: str, value: str, field_label2: str, value2: str):
        return [
            Paragraph(f"{field_label}:", label_style),
            Paragraph(value, value_style),
            Paragraph(f"{field_label2}:", label_style),
            Paragraph(value2, value_style),
        ]

    client_box = Table(
        [
            _row("Cliente", name, "CI", ruc_ci),
            _row("Telf", phone, "Dir", address),
        ],
        colWidths=[label_w, value_w, label_w, value_w],
    )

    client_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F9FAFB")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F9FAFB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    return client_box


# seccion tabla de productos
def _pdf_cell_text(text, style, *, align: str = "left") -> Paragraph:
    safe = (str(text) if text not in (None, "") else "-").replace("&", "&amp;")
    if align == "right":
        content = f'<para align="right">{safe}</para>'
    elif align == "center":
        content = f'<para align="center">{safe}</para>'
    else:
        content = safe
    return Paragraph(content, style)


def _product_table_styles(base: ParagraphStyle, primary_color: str) -> dict:
    return {
        "left": ParagraphStyle(
            "TblLeft",
            parent=base,
            alignment=TA_LEFT,
        ),
        "center": ParagraphStyle(
            "TblCenter",
            parent=base,
            alignment=TA_CENTER,
        ),
        "right": ParagraphStyle(
            "TblRight",
            parent=base,
            alignment=TA_RIGHT,
        ),
        "right_bold": ParagraphStyle(
            "TblRightBold",
            parent=base,
            fontName="Helvetica-Bold",
            alignment=TA_RIGHT,
            textColor=colors.HexColor(primary_color),
        ),
        "header": ParagraphStyle(
            "TblHeader",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "header_center": ParagraphStyle(
            "TblHeaderCenter",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "header_right": ParagraphStyle(
            "TblHeaderRight",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=TA_RIGHT,
        ),
    }


def _pdf_product_cell(item, style):
    product_name = item.detail or (
        item.product.name if getattr(item, "product", None) else "-"
    )
    parts = []
    image_path = quotation_item_image_path(item)
    if image_path and os.path.exists(image_path):
        try:
            thumb = Image(image_path)
            thumb._restrictSize(36, 36)
            parts.append(thumb)
        except Exception:
            pass
    parts.append(_pdf_cell_text(product_name, style, align="left"))
    return parts if len(parts) > 1 else parts[0]


def build_products_table(items, config):

    styles = getSampleStyleSheet()
    base_cell = ParagraphStyle(
        name="TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=10,
        wordWrap="CJK",
    )
    cell = _product_table_styles(base_cell, config.primary_color)

    data = [
        [
            Paragraph("CANT.", cell["header_right"]),
            Paragraph("PRODUCTO", cell["header"]),
            Paragraph("MEDIDA", cell["header"]),
            Paragraph("TEMÁTICA", cell["header"]),
            Paragraph("COLOR", cell["header"]),
            Paragraph("LOGO", cell["header_center"]),
            Paragraph("DESC%", cell["header_right"]),
            Paragraph("V. UNIT", cell["header_right"]),
            Paragraph("TOTAL", cell["header_right"]),
        ]
    ]

    for item in items:
        logo_display = logo_type_pdf_label(resolve_item_logo_type(item))
        item_discount = float(getattr(item, "item_discount", 0) or 0)

        data.append(
            [
                _pdf_cell_text(item.quantity, cell["right"], align="right"),
                _pdf_product_cell(item, cell["left"]),
                _pdf_cell_text(item.measure or "-", cell["left"], align="left"),
                _pdf_cell_text(item.theme or "-", cell["left"], align="left"),
                _pdf_cell_text(item.color or "-", cell["left"], align="left"),
                _pdf_cell_text(logo_display, cell["center"], align="center"),
                _pdf_cell_text(
                    f"{item_discount:.0f}%" if item_discount else "-",
                    cell["right"],
                    align="right",
                ),
                _pdf_cell_text(
                    f"${item.unit_price:.2f}",
                    cell["right"],
                    align="right",
                ),
                _pdf_cell_text(
                    f"${item.total:.2f}",
                    cell["right_bold"],
                    align="right",
                ),
            ]
        )

    col_widths = [30, 148, 42, 78, 44, 36, 32, 62, 58]
    table = Table(
        data,
        colWidths=col_widths,
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                # HEADER
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(config.primary_color)),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                # BODY
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#FAFAFA")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 1), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    return table


def build_design_totals_section(quotation, config, design_paths=None):

    styles = getSampleStyleSheet()

    # ===================================
    # IMÁGENES DE REFERENCIA
    # ===================================

    paths = [p for p in (design_paths or []) if p and os.path.exists(p)]
    image_elements = []

    for path in paths[:4]:
        try:
            img = Image(path)
            img._restrictSize(110, 80)
            image_elements.append(img)
        except Exception:
            continue

    if image_elements:
        if len(image_elements) == 1:
            image_row = [image_elements[0]]
        else:
            image_row = image_elements

        image_card = Table(
            [
                [
                    Paragraph(
                        "<b>IMÁGENES DE REFERENCIA</b>",
                        styles["BodyText"],
                    )
                ],
                [Table([image_row], colWidths=[350 / len(image_row)] * len(image_row))],
                [Paragraph("Referencia enviada por el cliente.", styles["BodyText"])],
            ],
            colWidths=[350],
        )
    else:
        image_card = None

    if image_card:
        image_card.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )

    # ===================================
    # RESUMEN
    # ===================================

    subtotal = float(quotation.subtotal or 0)

    discount_percent = float(getattr(quotation, "discount", 0) or 0)
    discount_amount = subtotal * (discount_percent / 100)
    subtotal_after_discount = subtotal - discount_amount

    iva_percent = float(quotation.iva or 0)
    iva_amount = subtotal_after_discount * (iva_percent / 100)

    shipping = float(getattr(quotation, "shipping_cost", None) or 0)

    summary_rows = [
        ["SUBTOTAL", f"${subtotal:.2f}"],
        ["DESCUENTO", f"${discount_amount:.2f}"],
        [f"IVA ({iva_percent:.2f}%)", f"${iva_amount:.2f}"],
    ]
    if shipping > 0:
        summary_rows.append(["ENVÍO", f"${shipping:.2f}"])

    summary_table = Table(
        summary_rows,
        colWidths=[90, 60],
    )

    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#E5E7EB")),
                ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    # ===================================
    # TOTAL
    # ===================================

    total_box = Table([["TOTAL", f"${quotation.total:.2f}"]], colWidths=[70, 70])

    total_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(config.primary_color)),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    totals_card = Table([[summary_table], [Spacer(1, 5)], [total_box]], colWidths=[150])

    totals_card.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    # ===================================
    # CONTENEDOR FINAL
    # ===================================

    if image_card:
        layout = Table([[image_card, totals_card]], colWidths=[380, 150])
    else:
        layout = Table([["", totals_card]], colWidths=[380, 150])

    layout.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    return layout


def build_benefits_section(config):

    styles = getSampleStyleSheet()

    card_color = colors.HexColor("#FAF8FF")

    border_color = colors.HexColor("#E9D5FF")

    benefits = [
        [
            Paragraph(
                f"""
                <font size="18" color="{config.primary_color}">
                🛡
                </font>
                """,
                styles["Normal"],
            ),
            Paragraph(
                f"""
                <font size="10">
                <b>CALIDAD GARANTIZADA</b>
                </font>
                <br/>
                <font size="8" color="#666666">
                Materiales de primera calidad y acabados profesionales.
                </font>
                """,
                styles["Normal"],
            ),
        ],
        [
            Paragraph(
                f"""
                <font size="18" color="{config.primary_color}">
                ⏰
                </font>
                """,
                styles["Normal"],
            ),
            Paragraph(
                """
                <font size="10">
                <b>ENTREGA PUNTUAL</b>
                </font>
                <br/>
                <font size="8" color="#666666">
                Cumplimos con las fechas acordadas.
                </font>
                """,
                styles["Normal"],
            ),
        ],
        [
            Paragraph(
                f"""
                <font size="18" color="{config.primary_color}">
                ✏
                </font>
                """,
                styles["Normal"],
            ),
            Paragraph(
                """
                <font size="10">
                <b>DISEÑO PERSONALIZADO</b>
                </font>
                <br/>
                <font size="8" color="#666666">
                Adaptado a tus necesidades y estilo.
                </font>
                """,
                styles["Normal"],
            ),
        ],
        [
            Paragraph(
                f"""
                <font size="18" color="{config.primary_color}">
                ☎
                </font>
                """,
                styles["Normal"],
            ),
            Paragraph(
                """
                <font size="10">
                <b>ATENCIÓN AL CLIENTE</b>
                </font>
                <br/>
                <font size="8" color="#666666">
                Siempre estamos para ayudarte.
                </font>
                """,
                styles["Normal"],
            ),
        ],
    ]

    table = Table([benefits], colWidths=[135, 135, 135, 135])

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), card_color),
                ("BOX", (0, 0), (-1, -1), 1, border_color),
                ("LINEAFTER", (0, 0), (2, 0), 1, border_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    return table

def build_payment_status_section(quotation, config):

    total = float(quotation.total or 0)
    total_paid = quotation.total_paid
    pending = quotation.pending_balance

    styles = getSampleStyleSheet()

    content = Paragraph(
        f"""
        <font size="8">
        <b>ESTADO DE PAGO</b>
        <br/>
        Total: <b>${total:.2f}</b>
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Abonado: <b>${total_paid:.2f}</b>
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Saldo: <b>${pending:.2f}</b>
        </font>
        """,
        styles["BodyText"],
    )

    table = Table(
        [[content]],
        colWidths=[530],
    )

    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F3FF")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    return table

def build_notes_section(config):

    styles = getSampleStyleSheet()
    notes_style = ParagraphStyle(
        "NotesCompact",
        parent=styles["BodyText"],
        fontSize=7,
        leading=8,
        spaceBefore=0,
        spaceAfter=0,
    )

    notes = Paragraph(
        f"""
        <b>CONDICIONES COMERCIALES</b><br/>
        • Vigencia: <b>{config.quotation_validity_days} días</b> desde la emisión.<br/>
        • Producción inicia tras aprobar diseño y confirmar el pago.<br/>
        • Valores en dólares americanos; sujetos a cambio por cantidad, material o especificaciones.<br/>
        <font color="{config.primary_color}"><i>{config.quotation_footer_text}</i></font>
        """,
        notes_style,
    )

    table = Table(
        [[notes]],
        colWidths=[530],
    )

    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    return table
