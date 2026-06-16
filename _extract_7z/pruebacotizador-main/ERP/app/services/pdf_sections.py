from reportlab.platypus import Table, TableStyle, Paragraph, Image, Spacer

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4

from reportlab.platypus.flowables import HRFlowable

import os


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
def build_products_table(items, config):

    styles = getSampleStyleSheet()
    table_cell_style = ParagraphStyle(
        name="TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        wordWrap="CJK",
    )

    data = [
        ["CANT.", "PRODUCTO", "MEDIDA", "TEMÁTICA", "COLOR", "LOGO", "V. UNIT", "TOTAL"]
    ]

    for item in items:

        product_name = item.detail or (
            item.product.name if getattr(item, "product", None) else "-"
        )

        logo_display = "Sí" if item.logo else "-"

        data.append(
            [
                Paragraph(str(item.quantity), table_cell_style),
                Paragraph(product_name, table_cell_style),
                Paragraph(item.measure or "-", table_cell_style),
                Paragraph(item.theme or "-", table_cell_style),
                Paragraph(item.color or "-", table_cell_style),
                Paragraph(logo_display, table_cell_style),
                Paragraph(f"${item.unit_price:.2f}", table_cell_style),
                Paragraph(f"${item.total:.2f}", table_cell_style),
            ]
        )

    table = Table(
        data,
        colWidths=[
            35,  # cantidad
            160,  # producto
            45,  # medida
            90,  # temática
            55,  # color
            35,  # logo
            60,  # unitario
            50,  # total
        ],
    )

    table.setStyle(
        TableStyle(
            [
                # HEADER
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(config.primary_color)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("TOPPADDING", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                # BODY
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
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
                ("TOPPADDING", (0, 1), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return table


def build_design_totals_section(quotation, config, image_path=None):

    styles = getSampleStyleSheet()

    # ===================================
    # IMAGEN DE REFERENCIA
    # ===================================

    if image_path:

        try:

            design_image = Image(image_path)

            design_image._restrictSize(240, 160)

        except:

            design_image = Paragraph("Sin imagen disponible", styles["Normal"])

    else:

        design_image = Paragraph("Sin imagen de referencia", styles["Normal"])

    image_card = Table(
        [
            [
                Paragraph(
                    "<b>IMAGEN DE REFERENCIA / DISEÑO PERSONALIZADO</b>",
                    styles["BodyText"],
                )
            ],
            [design_image],
            [Paragraph("Referencia enviada por el cliente.", styles["BodyText"])],
        ],
        colWidths=[350],
    )

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

    summary_table = Table(
        [
            ["SUBTOTAL", f"${subtotal:.2f}"],
            ["DESCUENTO", f"{discount:.2f}%"],
            [f"IVA ({quotation.iva:.2f}%)", f"${iva_amount:.2f}"],
        ],
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

    layout = Table([[image_card, totals_card]], colWidths=[380, 150])

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
