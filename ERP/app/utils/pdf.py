from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from reportlab.lib.pagesizes import A4

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

    # ====================================
    # DOCUMENT
    # ====================================

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    elements = []

    # ====================================
    # HEADER
    # ====================================

    company = Paragraph(
        """
        <font size=26 color='#7C3AED'>
        <b>INNOVA ARTE</b>
        </font>
        """,
        styles["Title"]
    )

    quotation_text = Paragraph(
        f"""
        <font size=14 color='#555555'>
        Cotización #{quotation.id}
        <br/>
        {datetime.now().strftime('%d/%m/%Y')}
        </font>
        """,
        styles["BodyText"]
    )

    header_table = Table([
        [company, quotation_text]
    ], colWidths=[350, 180])

    elements.append(header_table)

    elements.append(
        Spacer(1, 30)
    )

    # ====================================
    # CLIENT
    # ====================================

    client_title = Paragraph(
        """
        <font size=12 color='#888888'>
        CLIENTE
        </font>
        """,
        styles["BodyText"]
    )

    client_name = Paragraph(
        f"""
        <font size=18>
        <b>{client.name}</b>
        </font>
        """,
        styles["BodyText"]
    )

    client_phone = Paragraph(
        f"""
        <font size=11>
        {client.phone or ""}
        </font>
        """,
        styles["BodyText"]
    )

    client_address = Paragraph(
        f"""
        <font size=11 color='#666666'>
        {client.address or ""}
        </font>
        """,
        styles["BodyText"]
    )

    elements.append(client_title)
    elements.append(Spacer(1, 5))

    elements.append(client_name)
    elements.append(client_phone)
    elements.append(client_address)

    elements.append(
        Spacer(1, 30)
    )

    # ====================================
    # TABLE
    # ====================================

    data = [[

        "CANT",
        "PRODUCTO",
        "MEDIDA",
        "FORMA",
        "COLOR",
        "LOGO",
        "V. UNIT",
        "TOTAL"

    ]]

    for item in items:

        data.append([

            str(item.quantity),

            item.detail or "-",

            item.measure or "-",

            item.shape or "-",

            item.color or "-",

            item.logo or "-",

            f"${item.unit_price:.2f}",

            f"${item.total:.2f}"

        ])

    table = Table(

    data,

    colWidths=[

        40,   # CANT
        145,  # PRODUCTO
        75,   # MEDIDA
        75,   # FORMA
        70,   # COLOR
        50,   # LOGO
        60,   # V UNIT
        60    # TOTAL

    ]

)

    table.setStyle(

    TableStyle([

        # ====================================
        # HEADER
        # ====================================

        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            colors.HexColor("#E9D5FF")
        ),

        (
            "TEXTCOLOR",
            (0, 0),
            (-1, 0),
            colors.HexColor("#4C1D95")
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
            (-1, 0),
            9
        ),

        (
            "BOTTOMPADDING",
            (0, 0),
            (-1, 0),
            10
        ),

        (
            "TOPPADDING",
            (0, 0),
            (-1, 0),
            10
        ),

        # ====================================
        # BODY
        # ====================================

        (
            "FONTNAME",
            (0, 1),
            (-1, -1),
            "Helvetica"
        ),

        (
            "FONTSIZE",
            (0, 1),
            (-1, -1),
            8
        ),

        (
            "TEXTCOLOR",
            (0, 1),
            (-1, -1),
            colors.black
        ),

        (
            "GRID",
            (0, 0),
            (-1, -1),
            0.5,
            colors.HexColor("#D1D5DB")
        ),

        (
            "BOTTOMPADDING",
            (0, 1),
            (-1, -1),
            8
        ),

        (
            "TOPPADDING",
            (0, 1),
            (-1, -1),
            8
        ),

        (
            "LEFTPADDING",
            (0, 0),
            (-1, -1),
            6
        ),

        (
            "RIGHTPADDING",
            (0, 0),
            (-1, -1),
            6
        ),

        # ====================================
        # ALIGNMENTS
        # ====================================

        (
            "ALIGN",
            (0, 0),
            (-1, -1),
            "CENTER"
        ),

        (
            "VALIGN",
            (0, 0),
            (-1, -1),
            "MIDDLE"
        ),

        # PRODUCTO LEFT
        (
            "ALIGN",
            (1, 1),
            (1, -1),
            "LEFT"
        ),

        # ====================================
        # TOTAL COLUMN
        # ====================================

        (
            "TEXTCOLOR",
            (-1, 1),
            (-1, -1),
            colors.HexColor("#7C3AED")
        ),

        (
            "FONTNAME",
            (-1, 1),
            (-1, -1),
            "Helvetica-Bold"
        )

    ])

    )

    elements.append(table)

    elements.append(
        Spacer(1, 40)
    )

    # ====================================
    # TOTALS
    # ====================================

    subtotal = quotation.subtotal or quotation.total

    totals = Table([

        [
            "SUBTOTAL",
            f"${subtotal:.2f}"
        ],

        [
            "IVA",
            f"{quotation.iva:.2f}%"
        ],

        [
            "TOTAL",
            f"${quotation.total:.2f}"
        ]

    ], colWidths=[180, 120])

    totals.setStyle(

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
                12
            ),

            (
                "LINEBELOW",
                (0, 0),
                (-1, -2),
                1,
                colors.HexColor("#E9D5FF")
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                12
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                12
            ),

            # TOTAL

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
                "TEXTCOLOR",
                (0, -1),
                (-1, -1),
                colors.HexColor("#7C3AED")
            )

        ])

    )

    totals_wrapper = Table([
        ["", totals]
    ], colWidths=[250, 250])

    elements.append(totals_wrapper)

    elements.append(
        Spacer(1, 40)
    )

    # ====================================
    # FOOTER
    # ====================================

    footer = Paragraph(
        """
        <font size=10 color='#777777'>
        Gracias por confiar en INNOVA ARTE.
        <br/>
        Esta cotización tiene validez de 15 días.
        </font>
        """,
        styles["BodyText"]
    )

    elements.append(
        HRFlowable(
            width="100%",
            color=colors.HexColor("#E9D5FF")
        )
    )

    elements.append(
        Spacer(1, 15)
    )

    elements.append(footer)

    # ====================================
    # BUILD
    # ====================================

    doc.build(elements)