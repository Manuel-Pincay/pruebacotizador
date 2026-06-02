from logging import config

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

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from reportlab.platypus.flowables import HRFlowable

from datetime import datetime

import os

from app.models import quotation
from app.models.company_config import CompanyConfig

from app.services.pdf_sections import (
    build_header,
    build_client_section,
    build_products_table,
    build_design_totals_section
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
            iva_default=19
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

    # ====================================
    # header empresa
    # ====================================

    elements.append(
    build_header(
        quotation,
        config,
        styles
    )
    )

    elements.append(
        Spacer(1,15)
    )

    elements.append(
        HRFlowable(
            width="100%",
            thickness=2,
            color=colors.HexColor(
                config.primary_color
            )
        )
    )

    elements.append(
        Spacer(1,20)
    )

    # ====================================
    # CLIENT CARD
    # ====================================

    elements.append(
    build_client_section(
        quotation,
        config,
        styles
    )
)

    elements.append(
        Spacer(1,20)
    )
       
    elements.append(Spacer(1,20))
    # ====================================
    # TABLE
    # ====================================
    elements.append(
    build_products_table(
        items,
        config
    )
)

    elements.append(
        Spacer(1,18)
    )


    elements.append(Spacer(1, 18))

    # ====================================
    # DESIGN IMAGE
    # ====================================
    image_path = None

    if quotation.design_file:

        image_path = os.path.join(
            "uploads",
            quotation.design_file
        )

    elements.append(

        build_design_totals_section(
            quotation,
            config,
            image_path
        )

    )

    elements.append(
        Spacer(1,20)
    )

    
    # ====================================
    # BENEFITS SECTION
    # ====================================
    
    benefits_data = [[
        Paragraph(
            f"""
            <para align="center">
            <font size="10"><b>✓ Calidad Garantizada</b></font>
            <br/>
            <font size="8" color="#666666">Materiales de primera calidad</font>
            </para>
            """,
            styles['Normal']
        ),
        Paragraph(
            f"""
            <para align="center">
            <font size="10"><b>✓ Entrega Puntual</b></font>
            <br/>
            <font size="8" color="#666666">Cumplimos fechas acordadas</font>
            </para>
            """,
            styles['Normal']
        ),
        Paragraph(
            f"""
            <para align="center">
            <font size="10"><b>✓ Diseño Personalizado</b></font>
            <br/>
            <font size="8" color="#666666">Adaptado a tu necesidad</font>
            </para>
            """,
            styles['Normal']
        ),
        Paragraph(
            f"""
            <para align="center">
            <font size="10"><b>✓ Atención al Cliente</b></font>
            <br/>
            <font size="8" color="#666666">Soporte permanente</font>
            </para>
            """,
            styles['Normal']
        ),
    ]]
    
    benefits_table = Table(benefits_data, colWidths=[130, 130, 130, 130])
    benefits_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8F5FF')),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor(config.primary_color)),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 12),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#DDD6FE')),
    ]))
    
    elements.append(benefits_table)
    elements.append(Spacer(1, 20))

    # ====================================
    # FOOTER - PROFESSIONAL
    # ====================================
    
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor(config.primary_color)))
    elements.append(Spacer(1, 10))

    footer_company = Paragraph(f"<font size=10><b>{config.company_name}</b></font>", styles['Normal'])
    footer_contact = Paragraph(
        f"""
        <font size=8 color='#666666'>
        Dirección: {getattr(config, 'address', '-')}<br/>
        Tel: {getattr(config, 'phone', '-')}<br/>
        Email: {getattr(config, 'email', '-')}
        </font>
        """,
        styles['Normal']
    )
    
    footer_content = Table([[footer_company, footer_contact]], colWidths=[280, 220])
    footer_content.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'LEFT'),
    ]))
    
    elements.append(footer_content)
    elements.append(Spacer(1, 8))
    
    footer_message = Paragraph(f"<font size=8 color='#777777'><i>{config.quotation_footer_text}</i></font>", styles['Normal'])
    elements.append(footer_message)


    # ====================================
    # BUILD
    # ====================================

    doc.build(elements)
