from reportlab.platypus import (
    SimpleDocTemplate,
    Spacer,
)


from reportlab.lib.pagesizes import A4

from reportlab.lib import colors

from reportlab.lib.styles import getSampleStyleSheet

from reportlab.platypus.flowables import HRFlowable

from app.models.company_config import CompanyConfig
from app.utils.image_storage import resolve_design_path
from app.services.quotation_design_service import get_design_filenames

from app.services.pdf_sections import (
    build_header,
    build_client_section,
    build_products_table,
    build_design_totals_section,
    build_payment_status_section,
    build_notes_section,
)
from io import BytesIO


def generate_quotation_pdf(quotation, items, client, db=None):

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
            iva_default=0,
        )

    # ====================================
    # DOCUMENT
    # ====================================

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
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

    elements.append(Spacer(1, 12))

    elements.append(
        HRFlowable(
            width="100%", thickness=2, color=colors.HexColor(config.primary_color)
        )
    )

    elements.append(Spacer(1, 10))

    # ====================================
    # CLIENT CARD
    # ====================================

    elements.append(build_client_section(quotation, config, styles))

    elements.append(Spacer(1, 10))

    # ====================================
    # TABLE
    # ====================================
    elements.append(build_products_table(items, config))

    elements.append(Spacer(1, 18))

    # ====================================
    # DESIGN IMAGES + TOTALS
    design_paths = [
        path
        for filename in get_design_filenames(quotation)
        if (path := resolve_design_path(filename))
    ]

    elements.append(build_design_totals_section(quotation, config, design_paths))

    elements.append(Spacer(1, 12))

    elements.append(build_payment_status_section(quotation, config))

    elements.append(Spacer(1, 8))

    # ====================================
    # NOTES
    # ====================================
    elements.append(build_notes_section(config))

    elements.append(Spacer(1, 6))

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

    doc.build(elements, 
              onFirstPage=draw_footer, 
              onLaterPages=draw_footer)
    buffer.seek(0)

    return buffer