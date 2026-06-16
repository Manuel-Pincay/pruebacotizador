from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
NUM_COLS = 14
# Columnas de orden / impresión que se fusionan por OP
MERGE_COLS = (0, 1, 2, 3, 4, 5, 6, 7, 12, 13)  # + CLIENTE, ESTADO


def _period_label(filters: dict[str, Any] | None) -> str:
    filters = filters or {}
    if filters.get("month") and filters.get("year"):
        month = MONTH_NAMES.get(filters["month"], str(filters["month"]))
        return f"{month} {filters['year']}"
    if filters.get("year"):
        return str(filters["year"])
    return "Todos"


def _clip(text: str | None, limit: int) -> str:
    value = (text or "—").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _short_status(status: str | None) -> str:
    code = (status or "pendiente").lower()
    return STATUS_SHORT.get(code, TRACKING_STATUS_LABELS.get(code, code)[:8])


def _format_delivery(value) -> str:
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return "—"


def _groups_from_rows(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    order_keys: list[str] = []
    for row in rows:
        key = str(row.get("order_label") or row.get("quotation_id") or "sin-orden")
        if key not in buckets:
            buckets[key] = []
            order_keys.append(key)
        buckets[key].append(row)
    return [
        sorted(
            buckets[key],
            key=lambda item: item.get("item_number") or item.get("item_id") or 0,
        )
        for key in order_keys
    ]


def _groups_from_order_groups(groups: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    result: list[list[dict[str, Any]]] = []
    for group in groups:
        fabrication = {
            "order_label": group.get("order_label"),
            "quotation_id": group.get("quotation_id"),
            "client_name": group.get("client_name"),
            "delivery_date": group.get("delivery_date"),
            "file_name": group.get("file_name") or "",
            "material": group.get("material") or "",
            "size": group.get("size") or "",
            "usb_reference": group.get("usb_reference") or "",
            "copies": group.get("copies") or 0,
            "designer": group.get("designer") or "",
            "production_status": group.get("production_status"),
            "production_status_label": group.get("production_status_label"),
        }
        products = group.get("products") or []
        if not products:
            result.append([{**fabrication}])
            continue
        result.append([
            {**fabrication, **product}
            for product in products
        ])
    return result


def _compute_summary(groups: list[list[dict[str, Any]]]) -> dict[str, int]:
    total_items = sum(len(group) for group in groups)
    units = sum(int(row.get("quantity") or 0) for group in groups for row in group)
    return {
        "orders": len(groups),
        "total_items": total_items,
        "units": units,
    }


def _build_table_rows(
    groups: list[list[dict[str, Any]]],
    cell,
    cell_center,
) -> tuple[list[list], list[tuple], list[int]]:
    headers = [
        "ORDEN", "COT", "ENTREGA", "ARCHIVO", "MATERIAL", "MED.IMP", "USB", "COPIAS",
        "CANT", "PRODUCTO", "MED", "FORMA", "CLIENTE", "ESTADO",
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
        order_cell = Paragraph(_clip(first.get("order_label"), 10), cell_center)
        cot_cell = Paragraph(str(first.get("quotation_id") or "—"), cell_center)
        delivery_cell = Paragraph(_format_delivery(first.get("delivery_date")), cell_center)
        file_cell = Paragraph(_clip(first.get("file_name"), 18), cell)
        material_cell = Paragraph(_clip(first.get("material"), 10), cell_center)
        size_cell = Paragraph(_clip(first.get("size"), 10), cell_center)
        usb_cell = Paragraph(_clip(first.get("usb_reference"), 12), cell_center)
        copies_cell = Paragraph(str(first.get("copies") or "—"), cell_center)
        client_cell = Paragraph(_clip(first.get("client_name"), 18), cell)
        status_cell = Paragraph(_short_status(first.get("production_status")), cell_center)

        for index, row in enumerate(group):
            product_row: list = [""] * NUM_COLS
            product_row[8] = Paragraph(str(row.get("quantity") or 0), cell_center)
            product_row[9] = Paragraph(_clip(row.get("product_name"), 28), cell)
            product_row[10] = Paragraph(_clip(row.get("measure"), 10), cell_center)
            product_row[11] = Paragraph(_clip(row.get("theme"), 10), cell_center)

            if index == 0:
                product_row[0] = order_cell
                product_row[1] = cot_cell
                product_row[2] = delivery_cell
                product_row[3] = file_cell
                product_row[4] = material_cell
                product_row[5] = size_cell
                product_row[6] = usb_cell
                product_row[7] = copies_cell
                product_row[12] = client_cell
                product_row[13] = status_cell

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
        page_width, _ = landscape(A4)
        self.drawRightString(
            page_width - 8 * mm,
            5 * mm,
            f"Página {self._pageNumber} de {total_pages}",
        )
        self.restoreState()


def build_fabrication_condensed_pdf(
    rows: list[dict[str, Any]] | None = None,
    *,
    order_groups: list[dict[str, Any]] | None = None,
    config=None,
    filters: dict[str, Any] | None = None,
    issued_by: str = "Sistema ERP",
    fabricator_name: str = "",
) -> BytesIO:
    del config

    if order_groups is not None:
        groups = _groups_from_order_groups(order_groups)
    else:
        groups = _groups_from_rows(rows or [])

    cell = ParagraphStyle(
        "Cell",
        fontName="Helvetica",
        fontSize=FONT_SIZE,
        leading=FONT_SIZE + 1,
        alignment=TA_LEFT,
        textColor=colors.black,
    )
    cell_center = ParagraphStyle("CellCenter", parent=cell, alignment=TA_CENTER)
    header_line = ParagraphStyle(
        "HeaderLine",
        fontName="Helvetica-Bold",
        fontSize=6,
        leading=7,
        alignment=TA_LEFT,
    )
    summary_line = ParagraphStyle(
        "SummaryLine",
        fontName="Helvetica",
        fontSize=5.5,
        leading=6.5,
        alignment=TA_LEFT,
    )

    margin = 8 * mm
    page_width, _ = landscape(A4)
    usable_width = page_width - (2 * margin)

    issued_date = datetime.now().strftime("%d/%m/%Y")
    period = _period_label(filters)
    fab_part = f" &nbsp;|&nbsp; Fabricador: {_clip(fabricator_name, 20)}" if fabricator_name else ""
    completed_note = (
        "Incluye ya realizadas"
        if filters and filters.get("show_completed")
        else "Solo pendientes de fabricar"
    )

    header_text = (
        f"<b>CONDENSADO DE FABRICACIÓN</b> &nbsp;|&nbsp; "
        f"Fecha: {issued_date} &nbsp;|&nbsp; "
        f"Usuario: {_clip(issued_by, 24)}{fab_part} &nbsp;|&nbsp; "
        f"Período: {period} &nbsp;|&nbsp; {completed_note}"
    )

    summary = _compute_summary(groups)
    summary_text = (
        f"<b>Resumen:</b> {summary['orders']} órdenes &nbsp;|&nbsp; "
        f"{summary['total_items']} líneas producto &nbsp;|&nbsp; "
        f"{summary['units']} unidades"
    )

    col_ratios = [0.06, 0.04, 0.06, 0.12, 0.07, 0.07, 0.07, 0.05, 0.04, 0.20, 0.06, 0.06, 0.14, 0.06]
    col_widths = [usable_width * ratio for ratio in col_ratios]

    table_data, span_commands, block_end_rows = _build_table_rows(groups, cell, cell_center)

    style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), FONT_SIZE),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFEDD5")),
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
    doc.build([
        Paragraph(header_text, header_line),
        Spacer(1, 1.5 * mm),
        Paragraph(summary_text, summary_line),
        Spacer(1, 1.5 * mm),
        data_table,
    ])
    buffer.seek(0)
    return buffer
