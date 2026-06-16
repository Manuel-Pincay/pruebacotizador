from datetime import date, datetime, timedelta

from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy.orm import Session, joinedload

from app.models.production_order import ProductionOrder
from app.models.quotation import Quotation
from app.models.shipment import Shipment

PENDING_QUOTATION_EXPIRE_DAYS = 10

PRODUCTION_VISIBLE_QUOTATION_STATUSES = (
    "aprobada",
    "produccion",
    "enviada",
    "enviado",
    "entregada",
    "entregado",
)


def cancel_stale_pending_quotations(db: Session) -> int:
    """Cancela cotizaciones en pendiente con más de N días sin aprobar."""
    cutoff = datetime.utcnow() - timedelta(days=PENDING_QUOTATION_EXPIRE_DAYS)
    updated = (
        db.query(Quotation)
        .filter(
            Quotation.status == "pendiente",
            Quotation.created_at.isnot(None),
            Quotation.created_at < cutoff,
        )
        .update({Quotation.status: "cancelada"}, synchronize_session=False)
    )
    if updated:
        db.commit()
    return updated


INACTIVE_PRODUCTION_QUOTATION_STATUSES = (
    "pendiente",
    "cancelada",
    "cancelado",
)


def cleanup_inactive_production_orders(db: Session) -> int:
    """Elimina órdenes de producción ligadas a cotizaciones que no van a fábrica."""
    inactive_ids = [
        row[0]
        for row in db.query(Quotation.id)
        .filter(Quotation.status.in_(INACTIVE_PRODUCTION_QUOTATION_STATUSES))
        .all()
    ]
    if not inactive_ids:
        return 0
    deleted = (
        db.query(ProductionOrder)
        .filter(ProductionOrder.quotation_id.in_(inactive_ids))
        .delete(synchronize_session=False)
    )
    if deleted:
        db.commit()
    return deleted


def prepare_production_module(db: Session) -> None:
    cancel_stale_pending_quotations(db)
    cleanup_inactive_production_orders(db)


def quotation_visible_in_production(quotation) -> bool:
    if not quotation:
        return False
    status = (quotation.status or "").lower().strip()
    return status in PRODUCTION_VISIBLE_QUOTATION_STATUSES


def production_orders_base_query(db: Session):
    """Órdenes cuya cotización ya fue aprobada y entra en flujo productivo."""
    return (
        db.query(ProductionOrder)
        .join(Quotation, ProductionOrder.quotation_id == Quotation.id)
        .filter(Quotation.status.in_(PRODUCTION_VISIBLE_QUOTATION_STATUSES))
    )


def validate_production_status_change(order, status: str):
    from app.services.production_order_service import normalize_status, validate_fabrication_data

    stage = normalize_status(status)
    if stage == "produccion":
        try:
            validate_fabrication_data(order)
        except ValueError as exc:
            return HTMLResponse(
                content=f"<script>alert('{exc}'); window.history.back();</script>",
                status_code=400,
            )
    return None


def validate_shipment_for_sent(order, status: str, db: Session):
    from app.services.production_order_service import normalize_status

    if normalize_status(status) != "envio":
        return None
    shipment = (
        db.query(Shipment)
        .filter(Shipment.quotation_id == order.quotation_id)
        .first()
    )
    if shipment:
        return None
    return HTMLResponse(
        content=(
            f"<script>alert('Crea la guía de envío antes de marcar como Enviado.'); "
            f"window.location.href = '/shipments/new/{order.quotation_id}';</script>"
        ),
        status_code=400,
    )


def ensure_production_order(db: Session, quotation, user_id: int | None = None) -> ProductionOrder | None:
    from app.services.production_order_service import ensure_production_order as _ensure
    return _ensure(db, quotation, user_id=user_id)


def order_delivery_date(order: ProductionOrder) -> date | None:
    """Fecha de entrega efectiva: orden de producción o cotización."""
    if order.delivery_date:
        value = order.delivery_date
        return value.date() if isinstance(value, datetime) else value
    quotation = order.quotation
    if quotation and quotation.delivery_date:
        qd = quotation.delivery_date
        return qd.date() if isinstance(qd, datetime) else qd
    return None


COMPLETED_ORDER_STATUSES = ("despachado", "entregado", "cancelado")

from app.services.production_order_service import (  # noqa: E402
    PRODUCTION_ORDER_STATUSES,
    PRODUCTION_STATUS_COLORS as _PO_COLORS,
    PRODUCTION_STATUS_LABELS,
    PRODUCTION_STATUS_SEQUENCE,
    normalize_status,
    transition_status as po_transition_status,
)

PRODUCTION_ORDER_STATUSES = PRODUCTION_STATUS_SEQUENCE + ["cancelado"]

PRODUCTION_STATUS_COLORS = _PO_COLORS


def next_production_status(current: str | None) -> str | None:
    status = normalize_status(current)
    try:
        index = PRODUCTION_STATUS_SEQUENCE.index(status)
    except ValueError:
        return None
    if index + 1 < len(PRODUCTION_STATUS_SEQUENCE):
        return PRODUCTION_STATUS_SEQUENCE[index + 1]
    return None


def production_status_index(status: str | None) -> int:
    try:
        return PRODUCTION_STATUS_SEQUENCE.index(normalize_status(status))
    except ValueError:
        return 0


def sync_quotation_from_production(db: Session, order: ProductionOrder, new_status: str) -> None:
    del db
    quotation = order.quotation
    if not quotation:
        return
    stage = normalize_status(new_status)
    if stage in {"produccion"}:
        quotation.status = "produccion"
    elif stage == "envio":
        quotation.status = "enviado"
    elif stage == "entregado":
        quotation.status = "entregado"


def apply_production_status_change(
    order: ProductionOrder,
    new_status: str,
    db: Session,
) -> None:
    po_transition_status(db, order, new_status, force=True)


def production_order_delivery_meta(order: ProductionOrder) -> dict:
    delivery = order_delivery_date(order)
    today = date.today()
    if not delivery:
        return {
            "date": None,
            "label": "Sin fecha",
            "days_until": None,
            "is_overdue": False,
            "is_today": False,
            "urgency": "none",
        }
    days_until = (delivery - today).days
    is_overdue = days_until < 0 and (order.status or "") not in COMPLETED_ORDER_STATUSES
    is_today = days_until == 0
    if is_overdue:
        urgency = "overdue"
    elif is_today:
        urgency = "today"
    elif days_until <= 3:
        urgency = "soon"
    else:
        urgency = "normal"
    return {
        "date": delivery,
        "label": delivery.strftime("%d/%m/%Y"),
        "days_until": days_until,
        "is_overdue": is_overdue,
        "is_today": is_today,
        "urgency": urgency,
    }


def status_requirements_hint(status: str) -> str:
    from app.services.production_order_service import normalize_status

    hints = {
        "produccion": "Requiere datos de fabricación completos (archivo, material, medida, copias).",
        "envio": "Requiere guía de envío creada.",
    }
    return hints.get(normalize_status(status), "")


KANBAN_COLUMNS = tuple(
    {
        "status": code,
        "label": PRODUCTION_STATUS_LABELS.get(code, code),
        "accent": PRODUCTION_STATUS_COLORS.get(code, "slate"),
        "next_status": PRODUCTION_STATUS_SEQUENCE[i + 1] if i + 1 < len(PRODUCTION_STATUS_SEQUENCE) else None,
        "action_label": f"Avanzar a {PRODUCTION_STATUS_LABELS.get(PRODUCTION_STATUS_SEQUENCE[i + 1], '—')}" if i + 1 < len(PRODUCTION_STATUS_SEQUENCE) else None,
        "action_class": "bg-purple-600 hover:bg-purple-700",
    }
    for i, code in enumerate(PRODUCTION_STATUS_SEQUENCE)
)


def kanban_order_card(order: ProductionOrder) -> dict:
    quotation = order.quotation
    client = quotation.client if quotation else None
    items = list(quotation.items) if quotation and quotation.items else []
    return {
        "id": order.id,
        "quotation_id": order.quotation_id,
        "status": order.status,
        "priority": order.priority or "media",
        "designer": order.designer or "",
        "fabricator": order.fabricator or "",
        "client_name": client.name if client and client.name else "Sin cliente",
        "first_item": items[0].detail if items else "Sin productos",
        "extra_items": max(len(items) - 1, 0),
        "total": float(quotation.total or 0) if quotation else 0,
        "delivery_meta": production_order_delivery_meta(order),
        "detail_url": f"/production/{order.id}",
        "order": order,
    }


def build_kanban_columns(orders: list[ProductionOrder]) -> list[dict]:
    by_status: dict[str, list[ProductionOrder]] = {col["status"]: [] for col in KANBAN_COLUMNS}
    for order in orders:
        status = normalize_status(order.status)
        if status not in by_status:
            by_status.setdefault(status, []).append(order)
        else:
            by_status[status].append(order)

    columns = []
    for col in KANBAN_COLUMNS:
        status = col["status"]
        sorted_orders = sorted(
            by_status.get(status, []),
            key=lambda o: (
                order_delivery_date(o) is None,
                order_delivery_date(o) or date.max,
                o.id,
            ),
        )
        columns.append({
            **col,
            "count": len(sorted_orders),
            "orders": sorted_orders,
            "cards": [kanban_order_card(o) for o in sorted_orders],
        })
    return columns


def group_orders_by_status(orders: list[ProductionOrder]) -> dict[str, list[ProductionOrder]]:
    grouped = {col["status"]: [] for col in KANBAN_COLUMNS}
    for order in orders:
        status = (order.status or "pendiente").lower().strip()
        grouped.setdefault(status, []).append(order)
    return grouped


def status_column_config(status: str | None) -> dict:
    key = (status or "pendiente").lower().strip()
    for col in KANBAN_COLUMNS:
        if col["status"] == key:
            return col
    return KANBAN_COLUMNS[0]


def week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def parse_week_anchor(value: str, fallback: date) -> date:
    if not value:
        return week_start(fallback)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
        return week_start(parsed)
    except ValueError:
        return week_start(fallback)


def week_label(week_monday: date, today: date) -> str:
    week_sunday = week_monday + timedelta(days=6)
    month_names = [
        "", "ene", "feb", "mar", "abr", "may", "jun",
        "jul", "ago", "sep", "oct", "nov", "dic",
    ]
    range_text = (
        f"{week_monday.day}–{week_sunday.day} "
        f"{month_names[week_monday.month]}"
    )
    if week_monday.month != week_sunday.month:
        range_text = (
            f"{week_monday.day} {month_names[week_monday.month]} – "
            f"{week_sunday.day} {month_names[week_sunday.month]}"
        )
    if week_monday <= today <= week_sunday:
        return f"Esta semana ({range_text})"
    if week_monday == week_start(today + timedelta(weeks=1)):
        return f"Próxima semana ({range_text})"
    if week_sunday == week_start(today - timedelta(days=1)) + timedelta(days=6):
        return f"Semana pasada ({range_text})"
    return range_text.capitalize()


def _sort_orders_by_delivery(orders: list[ProductionOrder]) -> list[ProductionOrder]:
    return sorted(
        orders,
        key=lambda o: (
            order_delivery_date(o) is None,
            order_delivery_date(o) or date.max,
            (o.priority not in ("alta", "urgente"), o.priority != "alta"),
            o.id,
        ),
    )


def build_kanban_week_columns(
    orders: list[ProductionOrder],
    anchor_week: date,
    today: date,
    hide_delivered: bool = False,
    past_weeks: int = 1,
    future_weeks: int = 3,
) -> list[dict]:
    """Agrupa órdenes en columnas semanales respecto a anchor_week (lunes)."""
    offsets = list(range(-past_weeks, future_weeks + 1))
    buckets: dict[date, list[ProductionOrder]] = {
        anchor_week + timedelta(weeks=offset): [] for offset in offsets
    }
    overdue: list[ProductionOrder] = []
    later: list[ProductionOrder] = []
    no_date: list[ProductionOrder] = []

    window_start = anchor_week + timedelta(weeks=-past_weeks)
    window_end = anchor_week + timedelta(weeks=future_weeks, days=6)

    for order in orders:
        status = (order.status or "").lower().strip()
        if hide_delivered and status == "entregado":
            continue

        delivery = order_delivery_date(order)
        if not delivery:
            no_date.append(order)
            continue

        delivery_week = week_start(delivery)
        if (
            delivery < today
            and status not in COMPLETED_ORDER_STATUSES
            and status != "entregado"
        ):
            overdue.append(order)
            continue

        if delivery_week in buckets:
            buckets[delivery_week].append(order)
        elif delivery_week < window_start:
            overdue.append(order)
        elif delivery_week > window_end:
            later.append(order)
        else:
            buckets.setdefault(delivery_week, []).append(order)

    columns: list[dict] = []

    if overdue:
        columns.append({
            "kind": "overdue",
            "label": "Atrasadas",
            "sublabel": "Entrega vencida",
            "accent": "red",
            "count": len(overdue),
            "orders": _sort_orders_by_delivery(overdue),
            "is_current": False,
        })

    for offset in offsets:
        ws = anchor_week + timedelta(weeks=offset)
        week_orders = _sort_orders_by_delivery(buckets.get(ws, []))
        is_current = ws <= today <= ws + timedelta(days=6)
        accent = "purple" if is_current else ("indigo" if offset > 0 else "slate")
        columns.append({
            "kind": "week",
            "week_start": ws,
            "week_end": ws + timedelta(days=6),
            "label": week_label(ws, today),
            "sublabel": ws.strftime("%d/%m/%Y"),
            "accent": accent,
            "count": len(week_orders),
            "orders": week_orders,
            "is_current": is_current,
        })

    if later:
        columns.append({
            "kind": "later",
            "label": "Más adelante",
            "sublabel": "Fuera del rango visible",
            "accent": "gray",
            "count": len(later),
            "orders": _sort_orders_by_delivery(later),
            "is_current": False,
        })

    if no_date:
        columns.append({
            "kind": "no_date",
            "label": "Sin fecha",
            "sublabel": "Asignar entrega",
            "accent": "gray",
            "count": len(no_date),
            "orders": _sort_orders_by_delivery(no_date),
            "is_current": False,
        })

    return columns


ACTIVE_PRODUCTION_STATUSES = tuple(
    code for code in PRODUCTION_STATUS_SEQUENCE if code not in {"entregado", "cancelado"}
)

ADMIN_DASHBOARD_ORDERS_LIMIT = 10


def build_dashboard_production_summary(db: Session) -> dict:
    """KPIs y órdenes activas para el dashboard (entregas, atrasos)."""
    today = date.today()
    week_monday = week_start(today)
    week_sunday = week_monday + timedelta(days=6)

    orders = (
        production_orders_base_query(db)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client)
        )
        .filter(ProductionOrder.status.in_(ACTIVE_PRODUCTION_STATUSES))
        .all()
    )

    overdue = due_today = due_this_week = urgent = 0
    enriched = []

    for order in orders:
        meta = production_order_delivery_meta(order)
        if meta["is_overdue"]:
            overdue += 1
        if meta["is_today"]:
            due_today += 1
        if meta["date"] and week_monday <= meta["date"] <= week_sunday:
            due_this_week += 1
        if meta["urgency"] in ("overdue", "today", "soon"):
            urgent += 1
        quotation = order.quotation
        client = quotation.client if quotation else None
        enriched.append(
            {
                "order": order,
                "delivery_meta": meta,
                "client_name": client.name if client else "—",
                "quotation_id": quotation.id if quotation else None,
            }
        )

    enriched.sort(
        key=lambda row: (
            0 if row["delivery_meta"]["is_overdue"] else 1,
            row["delivery_meta"]["days_until"]
            if row["delivery_meta"]["days_until"] is not None
            else 9999,
        )
    )

    return {
        "active_count": len(orders),
        "overdue": overdue,
        "due_today": due_today,
        "due_this_week": due_this_week,
        "urgent": urgent,
        "recent_items": enriched[:5],
        "table_items": enriched[:ADMIN_DASHBOARD_ORDERS_LIMIT],
    }

