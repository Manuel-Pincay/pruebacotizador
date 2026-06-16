from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.condensed_service import TRACKING_STATUS_LABELS

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

STATUS_SHORT = {
    "pendiente": "Pend.",
    "diseno": "Diseño",
    "produccion": "Prod.",
    "envio": "Envío",
    "entregado": "Entreg.",
    "cancelado": "Cancel.",
}

FONT_SIZE = 5.5
ROW_PAD = 1
NUM_COLS = 11
MERGE_COLS = (0, 1, 2, 9, 10)  # ORDEN, COT, ENTREGA, ESTADO, CLIENTE


def _period_label(filters: dict[str, Any] | None) -> str:
    filters = filters or {}
    if filters.get("month") and filters.get("year"):
        month = MONTH_NAMES.get(filters["month"], str(filters["month"]))
        return f"{month} {filters['year']}"
    if filters.get("year"):
        return str(filters["year"])
    return "Todos"


def _short_status(status: str | None) -> str:
    code = (status or "pendiente").lower()
    return STATUS_SHORT.get(code, TRACKING_STATUS_LABELS.get(code, code)[:8])


def _clip(text: str | None, limit: int) -> str:
    value = (text or "—").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _compute_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    order_keys = {row.get("order_label") or row.get("quotation_id") for row in rows}
    return {
        "total_items": len(rows),
        "orders": len(order_keys),
        "pending": sum(
            1 for row in rows
            if (row.get("production_status") or "pendiente").lower() == "pendiente"
        ),
        "custom": sum(1 for row in rows if row.get("is_custom")),
        "units": sum(row.get("quantity") or 0 for row in rows),
        "in_production": sum(
            1 for row in rows
            if (row.get("production_status") or "").lower() in {"diseno", "produccion", "control_calidad", "empaque"}
        ),
        "ready": sum(
            1 for row in rows
            if (row.get("production_status") or "").lower() in {"listo", "entregado"}
        ),
    }


def _group_rows_by_order(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    order_keys: list[str] = []

    for row in rows:
        key = str(row.get("order_label") or row.get("quotation_id") or "sin-orden")
        if key not in buckets:
            buckets[key] = []
            order_keys.append(key)
        buckets[key].append(row)

    groups: list[list[dict[str, Any]]] = []
    for key in order_keys:
        groups.append(sorted(
            buckets[key],
            key=lambda item: item.get("item_number") or item.get("item_id") or 0,
        ))
    return groups


def _build_table_rows(
    groups: list[list[dict[str, Any]]],
    cell,
    cell_center,
) -> tuple[list[list], list[tuple], list[int]]:
    headers = [
        "ORDEN", "COT", "ENTREGA", "CANT", "PRODUCTO",
        "MEDIDA", "FORMA", "COLOR", "PERS", "ESTADO", "CLIENTE",
    ]
    table_data: list[list] = [
        [Paragraph(f"<b>{label}</b>", cell_center) for label in headers]
    ]
    span_commands: list[tuple] = []
    block_end_rows: list[int] = []
    row_idx = 1

    if not groups:
        empty = [Paragraph("Sin registros.", cell)] + [""] * (NUM_COLS - 1)
        table_data.append(empty)
        span_commands.append(("SPAN", (0, 1), (NUM_COLS - 1, 1)))
        return table_data, span_commands, block_end_rows

    for group in groups:
        first = group[0]
        start_row = row_idx
        delivery = (
            first["delivery_date"].strftime("%d/%m/%Y")
            if first.get("delivery_date") else "—"
        )
        status = _short_status(first.get("production_status"))
        order_cell = Paragraph(_clip(first.get("order_label"), 10), cell_center)
        cot_cell = Paragraph(str(first.get("quotation_id") or "—"), cell_center)
        delivery_cell = Paragraph(delivery, cell_center)
        status_cell = Paragraph(status, cell_center)
        client_cell = Paragraph(_clip(first.get("client_name"), 20), cell)

        for index, row in enumerate(group):
            product_row: list = [""] * NUM_COLS
            product_row[3] = Paragraph(str(row.get("quantity") or 0), cell_center)
            product_row[4] = Paragraph(_clip(row.get("product_name"), 30), cell)
            product_row[5] = Paragraph(_clip(row.get("measure"), 12), cell_center)
            product_row[6] = Paragraph(_clip(row.get("theme"), 12), cell_center)
            product_row[7] = Paragraph(_clip(row.get("color"), 12), cell_center)
            product_row[8] = Paragraph("P" if row.get("is_custom") else "N", cell_center)

            if index == 0:
                product_row[0] = order_cell
                product_row[1] = cot_cell
                product_row[2] = delivery_cell
                product_row[9] = status_cell
                product_row[10] = client_cell

            table_data.append(product_row)
            row_idx += 1

        end_row = row_idx - 1
        block_end_rows.append(end_row)
        if len(group) > 1:
            for col in MERGE_COLS:
                span_commands.append(("SPAN", (col, start_row), (col, end_row)))

    return table_data, span_commands, block_end_rows


class _NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_footer(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica", 5)
        self.setFillColor(colors.black)
        page_width, _ = landscape(A4)
        self.drawRightString(
            page_width - 8 * mm,
            5 * mm,
            f"Página {self._pageNumber} de {total_pages}",
        )
        self.restoreState()


def export_condensed_production_pdf(
    rows: list[dict[str, Any]],
    *,
    config=None,
    filters: dict[str, Any] | None = None,
    clients: list | None = None,
    issued_by: str = "Sistema ERP",
    observations: str = "",
) -> BytesIO:
    del config, clients, observations

    styles = getSampleStyleSheet()
    cell = ParagraphStyle(
        "Cell",
        fontName="Helvetica",
        fontSize=FONT_SIZE,
        leading=FONT_SIZE + 1,
        alignment=TA_LEFT,
        textColor=colors.black,
    )
    cell_center = ParagraphStyle(
        "CellCenter",
        parent=cell,
        alignment=TA_CENTER,
    )
    header_line = ParagraphStyle(
        "HeaderLine",
        fontName="Helvetica-Bold",
        fontSize=6,
        leading=7,
        alignment=TA_LEFT,
        textColor=colors.black,
    )
    summary_line = ParagraphStyle(
        "SummaryLine",
        fontName="Helvetica",
        fontSize=5.5,
        leading=6.5,
        alignment=TA_LEFT,
        textColor=colors.black,
    )

    margin = 8 * mm
    page_width, _ = landscape(A4)
    usable_width = page_width - (2 * margin)

    issued_date = datetime.now().strftime("%d/%m/%Y")
    period = _period_label(filters)
    header_text = (
        f"<b>CONDENSADO DE PRODUCCIÓN</b> &nbsp;|&nbsp; "
        f"Fecha: {issued_date} &nbsp;|&nbsp; "
        f"Usuario: {_clip(issued_by, 24)} &nbsp;|&nbsp; "
        f"Período: {period}"
    )

    summary = _compute_summary(rows)
    summary_text = (
        f"<b>Resumen:</b> {summary['total_items']} ítems &nbsp;|&nbsp; "
        f"{summary['orders']} órdenes &nbsp;|&nbsp; "
        f"{summary['units']} unidades &nbsp;|&nbsp; "
        f"<b>Pendientes: {summary['pending']}</b> &nbsp;|&nbsp; "
        f"En proceso: {summary['in_production']} &nbsp;|&nbsp; "
        f"Listos: {summary['ready']} &nbsp;|&nbsp; "
        f"Personalizados: {summary['custom']}"
    )

    col_ratios = [0.07, 0.04, 0.07, 0.04, 0.22, 0.08, 0.09, 0.08, 0.04, 0.07, 0.20]
    col_widths = [usable_width * ratio for ratio in col_ratios]

    groups = _group_rows_by_order(rows)
    table_data, span_commands, block_end_rows = _build_table_rows(groups, cell, cell_center)

    style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), FONT_SIZE),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), ROW_PAD),
        ("BOTTOMPADDING", (0, 0), (-1, -1), ROW_PAD),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
    ]

    for end_row in block_end_rows:
        style_commands.append(
            ("LINEBELOW", (0, end_row), (-1, end_row), 0.5, colors.black)
        )

    style_commands.extend(span_commands)

    data_table = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    data_table.setStyle(TableStyle(style_commands))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=10 * mm,
        canvasmaker=_NumberedCanvas,
    )

    story = [
        Paragraph(header_text, header_line),
        Spacer(1, 1.5 * mm),
        Paragraph(summary_text, summary_line),
        Spacer(1, 1.5 * mm),
        data_table,
    ]
    doc.build(story)
    buffer.seek(0)
    return buffer
