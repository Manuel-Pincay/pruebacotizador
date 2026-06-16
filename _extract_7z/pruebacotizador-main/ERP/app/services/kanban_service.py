"""Kanban de producción: planificación semanal + vista tabla escalable."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.client import Client
from app.models.product import Product
from app.models.production_order import ProductionOrder
from app.models.production_order_history import ProductionOrderHistory
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.services.production_helpers import (
    order_delivery_date,
    production_orders_base_query,
    week_start,
    parse_week_anchor,
)

from app.services.production_order_service import (
    PRODUCTION_STATUS_LABELS,
    PRODUCTION_STATUS_SEQUENCE,
    build_history_list,
    can_transition,
    normalize_status,
)

# Columnas horizontales del kanban (estado real de la orden)
KANBAN_STATUS_COLUMNS: list[dict[str, Any]] = [
    {"key": "pendiente", "label": "Pendiente", "accent": "slate"},
    {"key": "diseno", "label": "Diseño", "accent": "indigo"},
    {"key": "produccion", "label": "Producción", "accent": "purple"},
    {"key": "envio", "label": "Envío", "accent": "blue"},
    {"key": "entregado", "label": "Entregado", "accent": "green"},
]

KANBAN_STATUS_KEYS = [col["key"] for col in KANBAN_STATUS_COLUMNS]

KPI_KEYS = [
    ("pendiente", "Pendiente"),
    ("diseno", "Diseño"),
    ("produccion", "Producción"),
    ("envio", "Envío"),
    ("entregado", "Entregado"),
    ("overdue", "Atrasadas"),
]

MAX_CARDS_PER_COLUMN = 50


def _quotation_has_custom(quotation: Quotation | None) -> bool:
    if not quotation or not quotation.items:
        return False
    for item in quotation.items:
        if item.product_id is None:
            return True
        if item.product and item.product.custom:
            return True
    return False


def _total_quantity(quotation: Quotation | None) -> int:
    if not quotation or not quotation.items:
        return 0
    return sum(int(item.quantity or 0) for item in quotation.items)


def delivery_priority(order: ProductionOrder, today: date) -> dict[str, str]:
    delivery = order_delivery_date(order)
    if not delivery:
        return {"level": "normal", "label": "🟢 Normal", "days": None}
    days = (delivery - today).days
    if days <= 2:
        return {"level": "urgent", "label": "🔴 Urgente", "days": days}
    if days <= 7:
        return {"level": "soon", "label": "🟠 Próxima", "days": days}
    return {"level": "normal", "label": "🟢 Normal", "days": days}


def kanban_lane_for_order(order: ProductionOrder) -> str:
    """Compatibilidad: lane = estado normalizado."""
    status = normalize_status(order.status)
    return status if status in KANBAN_STATUS_KEYS else ""


def parse_kanban_week(value: str, fallback: date) -> date:
    """Acepta YYYY-Www (input type=week) o YYYY-MM-DD."""
    if not value:
        return week_start(fallback)
    upper = value.strip().upper()
    if "-W" in upper:
        try:
            year_part, week_part = upper.split("-W", 1)
            return date.fromisocalendar(int(year_part), int(week_part), 1)
        except (ValueError, IndexError):
            pass
    return parse_week_anchor(value, fallback)


def monday_to_week_input(week_monday: date) -> str:
    iso = week_monday.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def order_delivery_in_week(order: ProductionOrder, week_monday: date) -> bool:
    delivery = order_delivery_date(order)
    if not delivery:
        return False
    return week_start(delivery) == week_monday


def week_header_label(week_monday: date, today: date) -> tuple[str, str, int]:
    """Título, rango de fechas y número ISO de semana."""
    sunday = week_monday + timedelta(days=6)
    iso = week_monday.isocalendar()
    sublabel = _week_range_label(week_monday)
    if week_monday <= today <= sunday:
        title = f"Semana {iso.week} (actual)"
    else:
        title = f"Semana {iso.week}"
    return title, sublabel, iso.week


def filter_orders_by_week(
    orders: list[ProductionOrder],
    week_monday: date,
) -> list[ProductionOrder]:
    return [o for o in orders if order_delivery_in_week(o, week_monday)]


def week_bucket_for_order(order: ProductionOrder, today: date) -> str:
    status = normalize_status(order.status)
    if status in {"entregado", "cancelado"}:
        return "delivered"

    delivery = order_delivery_date(order)
    if delivery and delivery < today and status not in {"entregado", "cancelado"}:
        return "overdue"

    if not delivery:
        return "no_date"

    current_monday = week_start(today)
    delivery_monday = week_start(delivery)

    for index in range(4):
        bucket_monday = current_monday + timedelta(weeks=index)
        if delivery_monday == bucket_monday:
            return f"week_{index}"

    if delivery_monday < current_monday:
        return "overdue"
    return "later"


def week_column_label(key: str, today: date) -> tuple[str, str]:
    current_monday = week_start(today)
    labels = {
        "overdue": ("Atrasadas", "Entrega vencida"),
        "week_0": ("Semana actual", _week_range_label(current_monday)),
        "week_1": ("Semana +1", _week_range_label(current_monday + timedelta(weeks=1))),
        "week_2": ("Semana +2", _week_range_label(current_monday + timedelta(weeks=2))),
        "week_3": ("Semana +3", _week_range_label(current_monday + timedelta(weeks=3))),
    }
    return labels.get(key, (key, ""))


def _week_range_label(monday: date) -> str:
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"{monday.day}–{sunday.day}/{monday.month:02d}"
    return f"{monday.day}/{monday.month:02d} – {sunday.day}/{sunday.month:02d}"


def serialize_kanban_card(order: ProductionOrder, today: date) -> dict[str, Any]:
    quotation = order.quotation
    client = quotation.client if quotation else None
    items = list(quotation.items) if quotation and quotation.items else []
    status = normalize_status(order.status)
    priority = delivery_priority(order, today)
    delivery = order_delivery_date(order)
    next_st = None
    try:
        idx = PRODUCTION_STATUS_SEQUENCE.index(status)
        if idx + 1 < len(PRODUCTION_STATUS_SEQUENCE):
            next_st = PRODUCTION_STATUS_SEQUENCE[idx + 1]
    except ValueError:
        pass

    designer = order.designer or ""
    if not designer and order.assignee:
        designer = order.assignee.full_name or order.assignee.username or ""

    return {
        "id": order.id,
        "label": f"OP-{order.id:04d}",
        "quotation_id": order.quotation_id,
        "client_name": (client.name if client and client.name else "Sin cliente"),
        "total_items": len(items),
        "total_quantity": _total_quantity(quotation),
        "products_label": f"{len(items)} producto{'s' if len(items) != 1 else ''}",
        "delivery_date": delivery.isoformat() if delivery else "",
        "delivery_label": delivery.strftime("%d/%m") if delivery else "Sin fecha",
        "delivery_full": delivery.strftime("%d/%m/%Y") if delivery else "Sin fecha",
        "status": status,
        "status_label": PRODUCTION_STATUS_LABELS.get(status, status),
        "designer": designer or "—",
        "fabricator": order.fabricator or "—",
        "material": order.design_material or "—",
        "priority_level": priority["level"],
        "priority_label": priority["label"],
        "priority_days": priority["days"],
        "lane": kanban_lane_for_order(order),
        "week_bucket": week_bucket_for_order(order, today),
        "next_status": next_st,
        "next_status_label": PRODUCTION_STATUS_LABELS.get(next_st or "", ""),
        "can_advance": bool(next_st and can_transition(status, next_st)),
        "has_custom": _quotation_has_custom(quotation),
        "detail_url": f"/production/{order.id}",
    }


def _order_passes_filters(
    order: ProductionOrder,
    *,
    today: date,
    month: str = "",
    client_id: int | None = None,
    designer: str = "",
    status: str = "",
    material: str = "",
    custom_only: bool = False,
    hide_delivered: bool = True,
) -> bool:
    st = normalize_status(order.status)
    if hide_delivered and st in {"entregado", "cancelado"}:
        return False

    if status and st != normalize_status(status):
        return False

    if client_id:
        quotation = order.quotation
        if not quotation or quotation.client_id != client_id:
            return False

    if designer:
        card = serialize_kanban_card(order, today)
        if designer.lower() not in (card["designer"] or "").lower():
            if not order.assignee or designer.lower() not in (
                (order.assignee.full_name or "") + (order.assignee.username or "")
            ).lower():
                return False

    if material:
        if (order.design_material or "").lower() != material.lower():
            return False

    if custom_only and not _quotation_has_custom(order.quotation):
        return False

    if month:
        delivery = order_delivery_date(order)
        if not delivery:
            return False
        try:
            y, m = map(int, month.split("-", 1))
            if delivery.year != y or delivery.month != m:
                return False
        except ValueError:
            pass

    return True


def load_kanban_orders(db: Session) -> list[ProductionOrder]:
    return (
        production_orders_base_query(db)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client),
            joinedload(ProductionOrder.quotation)
            .joinedload(Quotation.items)
            .joinedload(QuotationItem.product),
            joinedload(ProductionOrder.assignee),
        )
        .order_by(ProductionOrder.id.asc())
        .all()
    )


def compute_kanban_kpis(orders: list[ProductionOrder], today: date) -> dict[str, int]:
    kpis = {key: 0 for key, _ in KPI_KEYS}
    for order in orders:
        st = normalize_status(order.status)
        if st in kpis:
            kpis[st] += 1

        delivery = order_delivery_date(order)
        if (
            delivery
            and delivery < today
            and st not in {"entregado", "cancelado"}
        ):
            kpis["overdue"] += 1
    return kpis


def build_status_kanban_board(
    orders: list[ProductionOrder],
    *,
    today: date,
    max_per_column: int = MAX_CARDS_PER_COLUMN,
) -> list[dict[str, Any]]:
    """Columnas horizontales por estado para la semana seleccionada."""
    by_status: dict[str, list[dict]] = {k: [] for k in KANBAN_STATUS_KEYS}

    for order in orders:
        st = normalize_status(order.status)
        if st not in by_status:
            continue
        by_status[st].append(serialize_kanban_card(order, today))

    columns: list[dict[str, Any]] = []
    for col_def in KANBAN_STATUS_COLUMNS:
        key = col_def["key"]
        cards = sorted(
            by_status[key],
            key=lambda c: (
                c["priority_level"] != "urgent",
                c["priority_level"] != "soon",
                c["delivery_date"] or "9999",
                c["id"],
            ),
        )
        columns.append({
            **col_def,
            "drop_status": key,
            "count": len(cards),
            "cards": cards[:max_per_column],
            "hidden_count": max(0, len(cards) - max_per_column),
        })

    return columns


def build_kanban_table_rows(
    orders: list[ProductionOrder],
    today: date,
) -> list[dict[str, Any]]:
    rows = [serialize_kanban_card(order, today) for order in orders]
    rows.sort(
        key=lambda r: (
            r["priority_level"] != "urgent",
            r["priority_level"] != "soon",
            r["delivery_date"] or "9999",
            r["id"],
        )
    )
    return rows


def get_order_panel_detail(db: Session, order_id: int) -> dict[str, Any] | None:
    order = (
        production_orders_base_query(db)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client),
            joinedload(ProductionOrder.quotation)
            .joinedload(Quotation.items)
            .joinedload(QuotationItem.product),
            joinedload(ProductionOrder.assignee),
            joinedload(ProductionOrder.history).joinedload(ProductionOrderHistory.author),
        )
        .filter(ProductionOrder.id == order_id)
        .first()
    )
    if not order:
        return None

    quotation = order.quotation
    items = []
    if quotation and quotation.items:
        for item in quotation.items:
            items.append({
                "detail": item.detail or (item.product.name if item.product else "—"),
                "quantity": item.quantity or 0,
                "measure": item.measure or "—",
                "color": item.color or "—",
                "material": item.product.material if item.product else "—",
            })

    today = date.today()
    card = serialize_kanban_card(order, today)
    history = build_history_list(order)

    return {
        **card,
        "observations": order.observations or order.design_notes or "",
        "design_file": order.design_file_name or "",
        "design_material": order.design_material or "",
        "design_size": order.design_size or "",
        "design_usb": order.design_usb_reference or "",
        "design_copies": order.design_copies or 0,
        "products": items,
        "history": history,
        "responsible_designer": order.designer or card["designer"],
        "responsible_fabricator": order.fabricator or "—",
    }


def validate_kanban_move(order: ProductionOrder, target_status: str) -> str | None:
    current = normalize_status(order.status)
    target = normalize_status(target_status)
    if not can_transition(current, target):
        return (
            f"No se puede pasar de {PRODUCTION_STATUS_LABELS.get(current, current)} "
            f"a {PRODUCTION_STATUS_LABELS.get(target, target)}."
        )
    if target == "produccion":
        from app.services.production_order_service import validate_fabrication_data
        try:
            validate_fabrication_data(order)
        except ValueError as exc:
            return str(exc)
    return None


def list_filter_options(db: Session, orders: list[ProductionOrder]) -> dict[str, Any]:
    clients: dict[int, str] = {}
    designers: set[str] = set()
    materials: set[str] = set()

    for order in orders:
        if order.quotation and order.quotation.client:
            clients[order.quotation.client_id] = order.quotation.client.name
        card = serialize_kanban_card(order, date.today())
        if card["designer"] and card["designer"] != "—":
            designers.add(card["designer"])
        if order.design_material:
            materials.add(order.design_material)

    return {
        "clients": sorted(clients.items(), key=lambda x: x[1]),
        "designers": sorted(designers),
        "materials": sorted(materials),
        "statuses": [(c, PRODUCTION_STATUS_LABELS[c]) for c in PRODUCTION_STATUS_SEQUENCE],
    }


def filter_orders(
    orders: list[ProductionOrder],
    *,
    today: date,
    month: str = "",
    client_id: int | None = None,
    designer: str = "",
    status: str = "",
    material: str = "",
    custom_only: bool = False,
    hide_delivered: bool = True,
) -> list[ProductionOrder]:
    return [
        order
        for order in orders
        if _order_passes_filters(
            order,
            today=today,
            month=month,
            client_id=client_id,
            designer=designer,
            status=status,
            material=material,
            custom_only=custom_only,
            hide_delivered=hide_delivered,
        )
    ]
