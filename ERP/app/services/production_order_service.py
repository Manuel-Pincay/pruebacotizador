"""Flujo unificado: 1 cotización → 1 orden de producción."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload

from app.models.production_order import ProductionOrder
from app.models.production_order_history import ProductionOrderHistory
from app.models.quotation import Quotation
from app.models.user import User

PRODUCTION_ORDER_STATUSES: list[tuple[str, str]] = [
    ("pendiente", "Pendiente"),
    ("diseno", "Diseño"),
    ("produccion", "Producción"),
    ("envio", "Envío"),
    ("entregado", "Entregado"),
    ("cancelado", "Cancelado"),
]

PRODUCTION_STATUS_LABELS = dict(PRODUCTION_ORDER_STATUSES)
PRODUCTION_STATUS_SEQUENCE = [code for code, _ in PRODUCTION_ORDER_STATUSES if code != "cancelado"]

DESIGN_PHASE_STATUSES = {"pendiente", "diseno"}
DESIGN_EDIT_STATUSES = {"pendiente", "diseno"}

DESIGN_MATERIALS = ["MDF", "Acrílico", "PVC", "Cartón", "Vinil", "Foami", "Otro"]
DESIGN_SIZES = ["120x90", "50x100", "10x10", "Retazo", "Plancha Completa", "A4", "A3"]
USB_REFERENCES = ["USB #1", "USB #2", "USB Azul", "USB Rojo", "USB Producción"]

LEGACY_STATUS_MAP = {
    "pendiente_diseno": "pendiente",
    "en_diseno": "diseno",
    "diseno_aprobado": "diseno",
    "pendiente_produccion": "produccion",
    "en_produccion": "produccion",
    "empaque": "produccion",
    "listo_despacho": "envio",
    "despachado": "envio",
    "enviado": "envio",
    "diseño": "diseno",
    "empacado": "produccion",
    "control_calidad": "produccion",
    "listo": "envio",
    "cancelada": "cancelado",
}

PRODUCTION_STATUS_COLORS = {
    "pendiente": "gray",
    "diseno": "indigo",
    "produccion": "purple",
    "envio": "blue",
    "entregado": "green",
    "cancelado": "red",
}


def fabrication_data_complete(order: ProductionOrder) -> bool:
    return bool(
        (order.design_file_name or "").strip()
        and (order.design_material or "").strip()
        and (order.design_size or "").strip()
        and (order.design_copies or 0) > 0
    )


def validate_fabrication_data(order: ProductionOrder) -> None:
    missing = []
    if not (order.design_file_name or "").strip():
        missing.append("archivo")
    if not (order.design_material or "").strip():
        missing.append("material")
    if not (order.design_size or "").strip():
        missing.append("medida")
    if not (order.design_copies or 0):
        missing.append("copias")
    if missing:
        raise ValueError(f"Complete datos de fabricación: {', '.join(missing)}.")


def normalize_status(status: str | None) -> str:
    code = (status or "pendiente").lower().strip()
    mapped = LEGACY_STATUS_MAP.get(code, code)
    if mapped in PRODUCTION_STATUS_LABELS:
        return mapped
    return "pendiente"


def _user_label(user: User | None) -> str:
    if not user:
        return "—"
    return user.full_name or user.username or "—"


def _deduct_inventory_for_quotation(db: Session, quotation: Quotation) -> None:
    from app.models.inventory_movement import InventoryMovement
    from app.models.product import Product

    if not quotation or not quotation.items:
        return
    for item in quotation.items:
        if not item.product_id:
            continue
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            continue
        previous_stock = product.stock or 0
        new_stock = previous_stock - (item.quantity or 0)
        if new_stock < 0:
            raise ValueError(
                f"Stock insuficiente para {product.name}. "
                f"Disponible: {previous_stock}, solicitado: {item.quantity}."
            )
        product.stock = new_stock
        db.add(
            InventoryMovement(
                product_id=product.id,
                movement_type="salida",
                quantity=-item.quantity,
                previous_stock=previous_stock,
                new_stock=new_stock,
                reason=f"Cotización #{quotation.id} → Producción",
            )
        )


def log_history(
    db: Session,
    order: ProductionOrder,
    *,
    status: str,
    notes: str = "",
    user_id: int | None = None,
) -> ProductionOrderHistory:
    entry = ProductionOrderHistory(
        production_order_id=order.id,
        status=normalize_status(status),
        notes=notes.strip() or None,
        created_by=user_id,
    )
    db.add(entry)
    return entry


def can_transition(current: str | None, target: str) -> bool:
    current_code = normalize_status(current)
    target_code = normalize_status(target)
    if target_code == "cancelado":
        return current_code != "entregado"
    if current_code == "cancelado":
        return False
    try:
        return PRODUCTION_STATUS_SEQUENCE.index(target_code) == PRODUCTION_STATUS_SEQUENCE.index(current_code) + 1
    except ValueError:
        return False


def ensure_production_order(
    db: Session,
    quotation: Quotation,
    *,
    user_id: int | None = None,
) -> ProductionOrder | None:
    q_status = (quotation.status or "").lower().strip()
    if q_status in ("pendiente", "cancelada", "cancelado", "borrador"):
        return None

    existing = db.query(ProductionOrder).filter(ProductionOrder.quotation_id == quotation.id).first()
    if existing:
        existing.status = normalize_status(existing.status)
        return existing

    order = ProductionOrder(
        quotation_id=quotation.id,
        delivery_date=quotation.delivery_date,
        priority="media",
        status="pendiente",
        observations="",
        design_copies=1,
    )
    db.add(order)
    db.flush()
    log_history(db, order, status="pendiente", notes="Orden creada al aprobar cotización.", user_id=user_id)
    return order


def get_production_order(db: Session, order_id: int) -> ProductionOrder | None:
    return (
        db.query(ProductionOrder)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client),
            joinedload(ProductionOrder.quotation).joinedload(Quotation.items),
            joinedload(ProductionOrder.history).joinedload(ProductionOrderHistory.author),
            joinedload(ProductionOrder.assignee),
            joinedload(ProductionOrder.design_completer),
        )
        .filter(ProductionOrder.id == order_id)
        .first()
    )


def get_production_order_by_quotation(db: Session, quotation_id: int) -> ProductionOrder | None:
    return (
        db.query(ProductionOrder)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client),
            joinedload(ProductionOrder.assignee),
            joinedload(ProductionOrder.history).joinedload(ProductionOrderHistory.author),
        )
        .filter(ProductionOrder.quotation_id == quotation_id)
        .first()
    )


def transition_status(
    db: Session,
    order: ProductionOrder,
    new_status: str,
    *,
    user: User | None = None,
    notes: str = "",
    force: bool = False,
) -> ProductionOrder:
    target = normalize_status(new_status)
    current = normalize_status(order.status)

    if not force and not can_transition(current, target):
        if not (target == "cancelado" and user and user.role == "admin"):
            raise ValueError(
                f"No se puede pasar de {PRODUCTION_STATUS_LABELS.get(current, current)} "
                f"a {PRODUCTION_STATUS_LABELS.get(target, target)}."
            )

    now = datetime.utcnow()
    if not order.started_at and target != "pendiente":
        order.started_at = now
    if target == "entregado":
        order.completed_at = now
    if target == "produccion" and normalize_status(order.status) == "diseno":
        validate_fabrication_data(order)
        order.design_completed_at = now
        order.design_completed_by = user.id if user else None

    quotation = order.quotation
    if target == "produccion" and quotation:
        _deduct_inventory_for_quotation(db, quotation)

    order.status = target
    order.updated_at = now
    log_history(db, order, status=target, notes=notes, user_id=user.id if user else None)

    if quotation:
        if target == "produccion":
            quotation.status = "produccion"
        elif target == "envio":
            quotation.status = "enviado"
        elif target == "entregado":
            quotation.status = "entregado"
        elif target == "cancelado":
            quotation.status = "cancelada"

    db.commit()
    db.refresh(order)
    return order


def update_design_fields(
    db: Session,
    order: ProductionOrder,
    *,
    file_name: str = "",
    material: str = "",
    size: str = "",
    usb_reference: str = "",
    notes: str = "",
    copies: int = 1,
    user: User | None = None,
) -> ProductionOrder:
    if material and material not in DESIGN_MATERIALS:
        raise ValueError("Material no válido.")

    if file_name:
        order.design_file_name = file_name.strip()
    if material:
        order.design_material = material
    if size:
        order.design_size = size.strip()
    order.design_usb_reference = usb_reference.strip() or None
    order.design_notes = notes.strip() or None
    order.design_copies = max(1, int(copies or 1))
    order.updated_at = datetime.utcnow()

    current = normalize_status(order.status)
    if current == "pendiente":
        transition_status(db, order, "diseno", user=user, notes="Inicio de diseño.")
    else:
        db.commit()
        db.refresh(order)
    return order


def approve_design(db: Session, order: ProductionOrder, *, user: User | None = None, notes: str = "") -> ProductionOrder:
    current = normalize_status(order.status)
    if current not in DESIGN_EDIT_STATUSES:
        raise ValueError("La orden no está en fase de diseño.")
    validate_fabrication_data(order)

    if current == "pendiente":
        transition_status(db, order, "diseno", user=user, notes="Inicio de diseño.")
        order = get_production_order(db, order.id) or order

    transition_status(
        db,
        order,
        "produccion",
        user=user,
        notes=notes or "Datos de fabricación listos — pasa a producción.",
    )
    return get_production_order(db, order.id) or order


def assign_designer(db: Session, order: ProductionOrder, designer_user_id: int | None) -> ProductionOrder:
    designer = db.query(User).filter(User.id == designer_user_id).first() if designer_user_id else None
    order.assigned_to_user_id = designer.id if designer else None
    order.designer = _user_label(designer) if designer else None
    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return order


def list_design_orders(
    db: Session,
    *,
    viewer_user_id: int | None = None,
    admin_view: bool = False,
) -> list[dict[str, Any]]:
    query = (
        db.query(ProductionOrder)
        .join(Quotation, ProductionOrder.quotation_id == Quotation.id)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client),
            joinedload(ProductionOrder.assignee),
        )
        .order_by(ProductionOrder.created_at.desc())
    )
    if not admin_view and viewer_user_id:
        query = query.filter(
            (ProductionOrder.assigned_to_user_id.is_(None))
            | (ProductionOrder.assigned_to_user_id == viewer_user_id)
        )

    rows: list[dict[str, Any]] = []
    for order in query.all():
        if normalize_status(order.status) not in DESIGN_PHASE_STATUSES:
            continue
        client = order.quotation.client if order.quotation else None
        rows.append(build_order_dict(order, client_name=client.name if client else "—"))
    return rows


def build_order_dict(order: ProductionOrder, *, client_name: str = "—") -> dict[str, Any]:
    status = normalize_status(order.status)
    return {
        "id": order.id,
        "order_label": f"OP-{order.id:04d}",
        "quotation_id": order.quotation_id,
        "client_name": client_name,
        "file_name": order.design_file_name or "",
        "material": order.design_material or "",
        "size": order.design_size or "",
        "usb_reference": order.design_usb_reference or "",
        "detail": order.design_notes or "",
        "copies": order.design_copies or 1,
        "status": status,
        "status_label": PRODUCTION_STATUS_LABELS.get(status, status),
        "assigned_to": order.assigned_to_user_id,
        "assigned_to_name": _user_label(order.assignee),
        "created_at": order.created_at,
    }


def build_history_list(order: ProductionOrder) -> list[dict[str, Any]]:
    return [
        {
            "status_label": PRODUCTION_STATUS_LABELS.get(normalize_status(entry.status), entry.status),
            "notes": entry.notes or "",
            "created_by_name": _user_label(entry.author),
            "created_at": entry.created_at,
        }
        for entry in sorted(order.history or [], key=lambda row: row.created_at or datetime.min)
    ]


class _NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.setFont("Helvetica", 5)
            self.drawRightString(200 * mm, 5 * mm, f"Pág. {self._pageNumber} de {total}")
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


def export_design_sheet_pdf(order_dict: dict[str, Any]) -> BytesIO:
    margin = 8 * mm
    page_width, _ = A4
    usable = page_width - 2 * margin
    cell = ParagraphStyle("Cell", fontName="Helvetica", fontSize=6, leading=7, alignment=TA_LEFT)
    cell_center = ParagraphStyle("CellC", parent=cell, alignment=TA_CENTER)
    title = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=8, leading=9, alignment=TA_LEFT)

    header = (
        f"<b>ORDEN DE PRODUCCIÓN {order_dict['order_label']}</b> | "
        f"Cot. #{order_dict.get('quotation_id')}"
    )
    table_data = [
        [Paragraph("<b>Archivo</b>", cell_center), Paragraph("<b>Material</b>", cell_center),
         Paragraph("<b>Medida</b>", cell_center), Paragraph("<b>USB</b>", cell_center),
         Paragraph("<b>Cant.</b>", cell_center), Paragraph("<b>Cliente</b>", cell_center)],
        [
            Paragraph(order_dict.get("file_name") or "—", cell),
            Paragraph(order_dict.get("material") or "—", cell_center),
            Paragraph(order_dict.get("size") or "—", cell_center),
            Paragraph(order_dict.get("usb_reference") or "—", cell_center),
            Paragraph(str(order_dict.get("copies") or 0), cell_center),
            Paragraph((order_dict.get("client_name") or "—")[:24], cell),
        ],
    ]
    if order_dict.get("detail"):
        table_data.append([Paragraph(f"<b>Obs:</b> {order_dict['detail']}", cell), "", "", "", "", ""])

    table = Table(table_data, colWidths=[usable * r for r in [0.28, 0.12, 0.12, 0.12, 0.08, 0.28]])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
    ]))

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=10 * mm, canvasmaker=_NumberedCanvas)
    doc.build([Paragraph(header, title), Spacer(1, 2 * mm), table])
    buffer.seek(0)
    return buffer
