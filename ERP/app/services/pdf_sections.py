from reportlab.platypus import Table, TableStyle, Paragraph, Image, Spacer

from app.services.logo_types import logo_type_pdf_label, resolve_item_logo_type
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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

    client_box = Table(
        [
            [Paragraph("<b>CLIENTE</b>", styles["Normal"])],
            [
                Paragraph(
                    f"<font size='16'><b>{client.name}</b></font>", styles["Normal"]
                )
            ],
            [Paragraph(f"Teléfono: {client.phone or '-'}", styles["Normal"])],
            [Paragraph(f"Dirección: {client.address or '-'}", styles["Normal"])],
        ],
        colWidths=[550],
    )

    client_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F9FAFB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    return client_box


# seccion tabla de productos
def _pdf_cell_text(text, style) -> Paragraph:
    safe = (str(text) if text not in (None, "") else "-").replace("&", "&amp;")
    return Paragraph(safe, style)


def _pdf_product_cell(item, style):
    product_name = item.detail or (
        item.product.name if getattr(item, "product", None) else "-"
    )
    parts = []
    image_path = quotation_item_image_path(item)
    if image_path and os.path.exists(image_path):
        try:
            thumb = Image(image_path)
            thumb._restrictSize(42, 42)
            parts.append(thumb)
        except Exception:
            pass
    parts.append(_pdf_cell_text(product_name, style))
    return parts if len(parts) > 1 else parts[0]


def build_products_table(items, config):

    styles = getSampleStyleSheet()
    table_cell_style = ParagraphStyle(
        name="TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        wordWrap="CJK",
    )

    data = [
        ["CANT.", "PRODUCTO", "MEDIDA", "TEMÁTICA", "COLOR", "LOGO", "V. UNIT", "TOTAL"]
    ]

    for item in items:
        logo_display = logo_type_pdf_label(resolve_item_logo_type(item))

        data.append(
            [
                _pdf_cell_text(item.quantity, table_cell_style),
                _pdf_product_cell(item, table_cell_style),
                _pdf_cell_text(item.measure, table_cell_style),
                _pdf_cell_text(item.theme, table_cell_style),
                _pdf_cell_text(item.color, table_cell_style),
                _pdf_cell_text(logo_display, table_cell_style),
                _pdf_cell_text(f"${item.unit_price:.2f}", table_cell_style),
                _pdf_cell_text(f"${item.total:.2f}", table_cell_style),
            ]
        )

    table = Table(
        data,
        colWidths=[32, 168, 48, 90, 50, 42, 42, 52],
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                # HEADER
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(config.primary_color)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                # BODY
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (6, 1), (7, -1), "RIGHT"),
                ("FONTNAME", (7, 1), (7, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (7, 1), (7, -1), colors.HexColor(config.primary_color)),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#FAFAFA")],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 1), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
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

    subtotal = quotation.subtotal or 0

    discount = getattr(quotation, "discount", 0)

    iva_amount = subtotal * quotation.iva / 100

    shipping = float(getattr(quotation, "shipping_cost", None) or 0)

    summary_rows = [
        ["SUBTOTAL", f"${subtotal:.2f}"],
        ["DESCUENTO", f"{discount:.2f}%"],
        [f"IVA ({quotation.iva:.2f}%)", f"${iva_amount:.2f}"],
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
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#E5E7EB")),
                ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
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
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
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
        layout = Table([[totals_card]], colWidths=[530])

    layout.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
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
        <font size="9">
        <b>ESTADO DE PAGO</b>
        <br/><br/>
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

    notes = Paragraph(
        f"""
        <font size="9">

        <b>CONDICIONES COMERCIALES</b>

        <br/><br/>

        • La presente cotización tiene una vigencia de
        <b>{config.quotation_validity_days} días</b>
        a partir de la fecha de emisión.

        <br/>

        • Los tiempos de producción comienzan una vez aprobado el diseño y confirmado el pago.

        <br/>

        • Los valores indicados están expresados en dólares americanos.

        <br/>

        • Los precios pueden variar si se modifican cantidades, materiales o especificaciones.

        <br/><br/>

        <font color="{config.primary_color}">
        <i>{config.quotation_footer_text}</i>
        </font>

        </font>
        """,
        styles["BodyText"]
    )

    table = Table(
        [[notes]],
        colWidths=[530]
    )

    table.setStyle(
        TableStyle([

            (
                "BOX",
                (0,0),
                (-1,-1),
                1,
                colors.HexColor("#E5E7EB")
            ),

            (
                "BACKGROUND",
                (0,0),
                (-1,-1),
                colors.HexColor("#FAFAFA")
            ),

            (
                "LEFTPADDING",
                (0,0),
                (-1,-1),
                12
            ),

            (
                "RIGHTPADDING",
                (0,0),
                (-1,-1),
                12
            ),

            (
                "TOPPADDING",
                (0,0),
                (-1,-1),
                10
            ),

            (
                "BOTTOMPADDING",
                (0,0),
                (-1,-1),
                10
            )

        ])
    )

    return table
