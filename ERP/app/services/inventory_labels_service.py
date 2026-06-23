"""Generación de PDF de etiquetas con código de barras (datos desde products)."""

from __future__ import annotations

from io import BytesIO

from reportlab.graphics.barcode import code128
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.product import Product

LABEL_WIDTH = 50 * mm
LABEL_HEIGHT = 30 * mm
PAGE_MARGIN_X = 4 * mm
PAGE_MARGIN_Y = 4 * mm
ALLOWED_QUANTITIES = (1, 5, 10, 20, 50, 100)


def normalize_label_quantity(value) -> int:
    try:
        qty = int(value)
    except (TypeError, ValueError):
        return 1
    if qty in ALLOWED_QUANTITIES:
        return qty
    return 1


def search_products(db, *, search: str = "", limit: int = 500) -> list[Product]:
    query = db.query(Product).order_by(Product.name.asc())
    term = (search or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            (Product.code.ilike(like)) | (Product.name.ilike(like))
        )
    return query.limit(limit).all()


def find_product_by_code(db, code: str) -> Product | None:
    normalized = (code or "").strip()
    if not normalized:
        return None
    return (
        db.query(Product)
        .filter(Product.code == normalized)
        .first()
    )


def expand_label_entries(items: list[tuple[Product, int]]) -> list[Product]:
    entries: list[Product] = []
    for product, qty in items:
        count = normalize_label_quantity(qty)
        for _ in range(count):
            entries.append(product)
    return entries


def _labels_per_page() -> tuple[int, int, int]:
    page_w, page_h = A4
    cols = max(1, int((page_w - 2 * PAGE_MARGIN_X) // LABEL_WIDTH))
    rows = max(1, int((page_h - 2 * PAGE_MARGIN_Y) // LABEL_HEIGHT))
    return cols, rows, cols * rows


def _clip_text(text: str | None, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _draw_single_label(c: canvas.Canvas, x: float, y: float, product: Product) -> None:
    code = (product.code or "").strip()
    name = _clip_text(product.name, 26)
    price = f"${float(product.price or 0):.2f}"

    c.setStrokeColorRGB(0.75, 0.75, 0.75)
    c.setLineWidth(0.25)
    c.rect(x, y, LABEL_WIDTH, LABEL_HEIGHT, stroke=1, fill=0)

    c.setFillColorRGB(0, 0, 0)
    content_top = y + LABEL_HEIGHT - 3 * mm

    if code:
        try:
            barcode = code128.Code128(
                code,
                barHeight=7 * mm,
                barWidth=0.16 * mm,
                humanReadable=0,
            )
            barcode_x = x + (LABEL_WIDTH - barcode.width) / 2
            barcode_y = content_top - barcode.height
            barcode.drawOn(c, barcode_x, barcode_y)
            text_y = barcode_y - 2.5 * mm
        except Exception:
            text_y = content_top - 4 * mm
            c.setFont("Helvetica", 6)
            c.drawCentredString(x + LABEL_WIDTH / 2, text_y, "[código inválido]")
    else:
        text_y = content_top - 4 * mm
        c.setFont("Helvetica", 6)
        c.drawCentredString(x + LABEL_WIDTH / 2, text_y, "[sin código]")

    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(x + LABEL_WIDTH / 2, text_y - 3.2 * mm, _clip_text(code, 18))

    c.setFont("Helvetica", 6)
    c.drawCentredString(x + LABEL_WIDTH / 2, text_y - 6.8 * mm, name)

    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x + LABEL_WIDTH / 2, y + 2.2 * mm, price)


def generate_labels_pdf(products_with_qty: list[tuple[Product, int]]) -> BytesIO:
    entries = expand_label_entries(products_with_qty)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4
    cols, rows, per_page = _labels_per_page()

    if not entries:
        pdf.setFont("Helvetica", 12)
        pdf.drawString(20 * mm, page_h - 20 * mm, "No hay etiquetas seleccionadas.")
        pdf.showPage()
        pdf.save()
        buffer.seek(0)
        return buffer

    for index, product in enumerate(entries):
        position = index % per_page
        if index > 0 and position == 0:
            pdf.showPage()

        col = position % cols
        row = position // cols
        x = PAGE_MARGIN_X + col * LABEL_WIDTH
        y = page_h - PAGE_MARGIN_Y - (row + 1) * LABEL_HEIGHT
        _draw_single_label(pdf, x, y, product)

    pdf.save()
    buffer.seek(0)
    return buffer
