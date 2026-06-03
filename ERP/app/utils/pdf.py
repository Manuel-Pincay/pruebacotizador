from annotated_types import doc
from reportlab.platypus import (
    SimpleDocTemplate,
    Spacer,
)


from reportlab.lib.pagesizes import A4

from reportlab.lib import colors

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from reportlab.platypus.flowables import HRFlowable

from datetime import datetime

import os

from app.models.company_config import CompanyConfig

from app.services.pdf_sections import (
    build_benefits_section,
    build_header,
    build_client_section,
    build_products_table,
    build_design_totals_section,
    build_notes_section,
)


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
            iva_default=19,
        )

    # ====================================
    # DOCUMENT
    # ====================================

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28,
    )

    styles = getSampleStyleSheet()

    elements = []

    # funcion fotter

    # ====================================
    # header empresa
    # ====================================

    elements.append(build_header(quotation, config, styles))

    elements.append(Spacer(1, 15))

    elements.append(
        HRFlowable(
            width="100%", thickness=2, color=colors.HexColor(config.primary_color)
        )
    )

    elements.append(Spacer(1, 20))

    # ====================================
    # CLIENT CARD
    # ====================================

    elements.append(build_client_section(quotation, config, styles))

    elements.append(Spacer(1, 20))

    elements.append(Spacer(1, 20))
    # ====================================
    # TABLE
    # ====================================
    elements.append(build_products_table(items, config))

    elements.append(Spacer(1, 18))

    elements.append(Spacer(1, 18))

    # ====================================
    # DESIGN IMAGE
    # ====================================
    image_path = None

    if quotation.design_file:

        image_path = os.path.join(
            "uploads",
            "products",
            quotation.design_file
        )

        print("IMAGE PATH:", image_path)
        print("EXISTS:", os.path.exists(image_path))

    elements.append(build_design_totals_section(quotation, config, image_path))

    elements.append(Spacer(1, 20))

    # ====================================
    # BENEFITS SECTION
    # ====================================

    # ====================================
    # NOTES
    # ====================================
    elements.append(build_notes_section(config))

    elements.append(Spacer(1, 15))

    # ====================================
    # BUILD PDF
    # ====================================
    # ====================================
    # FOOTER EN TODAS LAS PAGINAS
    # ====================================

    def draw_footer(canvas, doc):

        canvas.saveState()

        width, height = doc.pagesize

        footer_y = 20

        canvas.setStrokeColor(colors.HexColor(config.primary_color))

        canvas.line(25, footer_y + 12, width - 25, footer_y + 12)

        canvas.setFont("Helvetica", 8)

        canvas.setFillColor(colors.HexColor("#666666"))

        canvas.drawString(30, footer_y, config.company_name)

        canvas.drawCentredString(width / 2, footer_y, getattr(config, "phone", ""))

        canvas.drawRightString(width - 30, footer_y, f"Página {canvas.getPageNumber()}")

        canvas.restoreState()

    # ====================================
    # GENERAR PDF
    # ====================================

    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
