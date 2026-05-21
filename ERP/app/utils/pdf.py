from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus.flowables import HRFlowable
from datetime import datetime


def generate_quotation_pdf(
    quotation,
    items,
    client,
    filename
):

    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()

    elements = []

    # ====================================
    # HEADER
    # ====================================

    title = Paragraph(
        """
        <font size=28 color='#C084C5'>
        <b>Cotización</b>
        </font>
        """,
        styles["Title"]
    )

    date_text = Paragraph(
        f"""
        <font size=14>
        {datetime.now().strftime('%d de %B del %Y')}
        </font>
        """,
        styles["BodyText"]
    )

    header_table = Table([
        [title, date_text]
    ], colWidths=[350, 180])

    elements.append(header_table)

    elements.append(
        Spacer(1, 40)
    )

    # ====================================
    # CLIENT
    # ====================================

    client_name = Paragraph(
        f"""
        <font size=18>
        <b>{client.name}</b>
        </font>
        """,
        styles["BodyText"]
    )

    elements.append(client_name)

    elements.append(
        Spacer(1, 40)
    )

    # ====================================
    # ITEMS TABLE
    # ====================================

    data = [[
        "CANTIDAD",
        "DETALLE",
        "V. UNITARIO",
        "TOTAL"
    ]]

    for item in items:

        data.append([

            str(item.quantity),

            item.detail,

            f"${item.unit_price:.2f}",

            f"${item.total:.2f}"

        ])

    table = Table(
        data,
        colWidths=[60, 300, 100, 100]
    )

    table.setStyle(

        TableStyle([

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#E8B8E8")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.black
            ),

            (
                "FONTNAME",
                (0, 0),
                (-1, 0),
                "Helvetica-Bold"
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                8
            ),

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.black
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, 0),
                6
            )

        ])

    )

    elements.append(table)

    elements.append(
        Spacer(1, 80)
    )

    # ====================================
    # TOTALS
    # ====================================

    subtotal = quotation.subtotal or quotation.total

    total_box = Table([

        ["SUBTOTAL", f"${subtotal:.2f}"],

        ["IVA", f"${quotation.iva:.2f}"],

        ["TOTAL", f"${quotation.total:.2f}"]

    ], colWidths=[180, 100])

    total_box.setStyle(

        TableStyle([

            (
                "FONTNAME",
                (0, 0),
                (-1, -1),
                "Helvetica"
            ),

            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                14
            ),

            (
                "LINEBELOW",
                (0, 0),
                (-1, -2),
                1,
                colors.HexColor("#E8B8E8")
            ),

            (
                "FONTNAME",
                (0, -1),
                (-1, -1),
                "Helvetica-Bold"
            ),

            (
                "FONTSIZE",
                (0, -1),
                (-1, -1),
                18
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                10
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                10
            )

        ])

    )

    totals_wrapper = Table([
        ["", total_box]
    ], colWidths=[250, 300])

    elements.append(totals_wrapper)

    doc.build(elements)