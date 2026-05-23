from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)

from reportlab.lib.pagesizes import A4

from reportlab.lib import colors

from reportlab.lib.styles import getSampleStyleSheet

from reportlab.platypus.flowables import HRFlowable

from datetime import datetime

import os

from app.models.company_config import CompanyConfig


def generate_quotation_pdf(quotation, items, client, filename, db=None):

    # ====================================
    # GET COMPANY CONFIG
    # ====================================

    config = None
    if db:
        config = db.query(CompanyConfig).first()
    
    # Use defaults if no config found
    if not config:
        from types import SimpleNamespace
        config = SimpleNamespace(
            company_name="SISTEMA ERP",
            logo=None,
            primary_color="#7C3AED",
            secondary_color="#E9D5FF",
            accent_color="#4C1D95",
            quotation_footer_text="Gracias por confiar en SISTEMA ERP.",
            quotation_validity_days=15,
            iva_default=19
        )

    # ====================================
    # DOCUMENT
    # ====================================

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )

    styles = getSampleStyleSheet()

    elements = []

    # ====================================
    # HEADER
    # ====================================

    logo_path = None
    
    # Try to use dynamic logo first
    if config and config.logo:
        logo_path = os.path.join("uploads", "logos", config.logo)
    
    # Fall back to static logo
    if not logo_path or not os.path.exists(logo_path):
        logo_path = "app/static/logo.png"

    if os.path.exists(logo_path):

        logo = Image(logo_path, width=120, height=60)

    else:

        logo = Paragraph(
            f"""
            <font size=26 color='{config.primary_color}'>
            <b>{config.company_name}</b>
            </font>
            """,
            styles["Title"],
        )

    quotation_text = Paragraph(
        f"""
        <font size=12 color='#555555'>

        <b>Cotización #{quotation.id}</b>

        <br/><br/>

        Fecha:
        {
            quotation.created_at.strftime('%d/%m/%Y')
            if quotation.created_at else datetime.now().strftime('%d/%m/%Y')
        }

        <br/>

        Entrega:
        {
            quotation.delivery_date.strftime('%d/%m/%Y')
            if quotation.delivery_date else "-"
        }

        <br/>

        Estado:
        {quotation.status.upper()}

        </font>
        """,
        styles["BodyText"],
    )

    header_table = Table([[logo, quotation_text]], colWidths=[350, 180])

    elements.append(header_table)

    elements.append(Spacer(1, 30))

    # ====================================
    # CLIENT
    # ====================================

    client_title = Paragraph(
        """
        <font size=12 color='#888888'>
        CLIENTE
        </font>
        """,
        styles["BodyText"],
    )

    client_name = Paragraph(
        f"""
        <font size=18>
        <b>{client.name}</b>
        </font>
        """,
        styles["BodyText"],
    )

    client_phone = Paragraph(
        f"""
        <font size=11>
        {client.phone or ""}
        </font>
        """,
        styles["BodyText"],
    )

    client_address = Paragraph(
        f"""
        <font size=11 color='#666666'>
        {client.address or ""}
        </font>
        """,
        styles["BodyText"],
    )

    elements.append(client_title)

    elements.append(Spacer(1, 5))

    elements.append(client_name)

    elements.append(client_phone)

    elements.append(client_address)

    elements.append(Spacer(1, 30))

    # ====================================
    # TABLE
    # ====================================

    data = [
        ["CANT", "PRODUCTO", "MEDIDA", "TEMÁTICA", "COLOR", "LOGO", "V. UNIT", "TOTAL"]
    ]

    for item in items:

        data.append(
            [
                str(item.quantity),
                item.detail or "-",
                item.measure or "-",
                item.theme or "-",
                item.color or "-",
                item.logo or "-",
                f"${item.unit_price:.2f}",
                f"${item.total:.2f}",
            ]
        )

    table = Table(data, colWidths=[40, 145, 75, 75, 70, 50, 60, 60])

    table.setStyle(
        TableStyle(
            [
                # HEADER
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(config.secondary_color)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(config.accent_color)),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                # BODY
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                ("TOPPADDING", (0, 1), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                # ALIGN
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                # PRODUCTO LEFT
                ("ALIGN", (1, 1), (1, -1), "LEFT"),
                # TOTAL
                ("TEXTCOLOR", (-1, 1), (-1, -1), colors.HexColor(config.primary_color)),
                ("FONTNAME", (-1, 1), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )

    elements.append(table)

    elements.append(Spacer(1, 30))

    # ====================================
    # DESIGN IMAGE
    # ====================================

    if quotation.design_file:

        image_path = os.path.join("uploads", "designs", quotation.design_file)

        if os.path.exists(image_path):

            design_title = Paragraph(
                """
                <font size=14>
                <b>Diseño Referencial</b>
                </font>
                """,
                styles["BodyText"],
            )

            elements.append(design_title)

            elements.append(Spacer(1, 15))

            design_image = Image(image_path, width=250, height=250)

            elements.append(design_image)

            elements.append(Spacer(1, 30))

    # ====================================
    # TOTALS
    # ====================================

    subtotal = quotation.subtotal or quotation.total

    totals = Table(
        [
            ["SUBTOTAL", f"${subtotal:.2f}"],
            ["IVA", f"{quotation.iva:.2f}%"],
            ["TOTAL", f"${quotation.total:.2f}"],
        ],
        colWidths=[180, 120],
    )

    totals.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("LINEBELOW", (0, 0), (-1, -2), 1, colors.HexColor(config.secondary_color)),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                # TOTAL
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 18),
                ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor(config.primary_color)),
            ]
        )
    )

    totals_wrapper = Table([["", totals]], colWidths=[250, 250])

    elements.append(totals_wrapper)

    elements.append(Spacer(1, 40))

    # ====================================
    # FOOTER
    # ====================================

    footer = Paragraph(
        f"""
        <font size=10 color='#777777'>

        {config.quotation_footer_text}

        <br/><br/>

        Esta cotización tiene validez de {config.quotation_validity_days} días.

        </font>
        """,
        styles["BodyText"],
    )

    elements.append(HRFlowable(width="100%", color=colors.HexColor(config.secondary_color)))

    elements.append(Spacer(1, 15))

    elements.append(footer)

    # ====================================
    # BUILD
    # ====================================

    doc.build(elements)
