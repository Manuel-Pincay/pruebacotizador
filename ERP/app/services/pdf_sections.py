from reportlab.platypus import Table, TableStyle, Paragraph, Image, Spacer

from reportlab.lib import colors

from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.styles import getSampleStyleSheet
import os


def build_header(quotation, config, styles):

    created = quotation.created_at.strftime("%d/%m/%Y")

    entrega = (
        quotation.delivery_date.strftime("%d/%m/%Y") if quotation.delivery_date else "-"
    )

    estado = quotation.status or "Pendiente"

    logo_path = None

    if config.logo:

        temp_path = os.path.join("uploads", config.logo)

        if os.path.exists(temp_path):
            logo_path = temp_path

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


from reportlab.platypus import Table
from reportlab.platypus import TableStyle
from reportlab.platypus import Paragraph

from reportlab.lib import colors


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
                str(item.quantity),
                product_name,
                item.measure or "-",
                item.theme or "-",
                item.color or "-",
                logo_display,
                f"${item.unit_price:.2f}",
                f"${item.total:.2f}",
            ]
        )

    table = Table(
        data,
        colWidths=[
            40,  # cantidad
            135,  # producto
            65,  # medida
            95,  # temática
            65,  # color
            45,  # logo
            55,  # unitario
            60,  # total
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

    # ==========================
    # IMAGEN
    # ==========================

    if image_path:

        try:

            design_image = Image(image_path, width=260, height=200)

        except:

            design_image = Paragraph("Sin imagen", styles["Normal"])

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
        ]
    )

    image_card.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                ("ROUNDEDCORNERS", [10, 10, 10, 10]),
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )

    # ==========================
    # TOTALES
    # ==========================

    subtotal = quotation.subtotal or 0

    discount = getattr(quotation, "discount", 0)

    iva_amount = subtotal * quotation.iva / 100

    summary_table = Table(
        [
            ["SUBTOTAL", f"${subtotal:.2f}"],
            ["DESCUENTO", f"{discount:.2f}%"],
            [f"IVA ({quotation.iva:.2f}%)", f"${iva_amount:.2f}"],
        ],
        colWidths=[120, 80],
    )

    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#E5E7EB")),
                ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#E5E7EB")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    total_box = Table([["TOTAL", f"${quotation.total:.2f}"]], colWidths=[120, 100])

    total_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(config.primary_color)),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ]
        )
    )

    totals_card = Table([[summary_table], [total_box]])

    totals_card.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    # ==========================
    # CONTENEDOR
    # ==========================

    layout = Table(
    [[
        image_card,
        totals_card
    ]],
    colWidths=[280,140]
)

    layout.setStyle(
        TableStyle([
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),0),
            ("RIGHTPADDING",(0,0),(-1,-1),0),
        ])
    )

    return layout