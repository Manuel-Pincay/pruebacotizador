from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from datetime import date, datetime, time, timedelta
from calendar import monthrange
from collections import defaultdict

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.auth.auth_handler import role_required

from app.models.production_order import ProductionOrder
from app.models.quotation import Quotation
from app.models.shipment import Shipment
from app.services.production_helpers import (
    validate_production_status_change,
    validate_shipment_for_sent,
    order_delivery_date,
    COMPLETED_ORDER_STATUSES,
    prepare_production_module,
    production_orders_base_query,
    quotation_visible_in_production,
    ensure_production_order,
    apply_production_status_change,
    next_production_status,
    production_order_delivery_meta,
    PRODUCTION_ORDER_STATUSES,
    PRODUCTION_STATUS_LABELS,
    production_status_index,
    status_requirements_hint,
    build_kanban_columns,
    group_orders_by_status,
    build_kanban_week_columns,
    parse_week_anchor,
    week_start,
    status_column_config,
)

router = APIRouter(
    prefix="/production",
    tags=["production"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config

_PRODUCTION_ORDER_LOAD = (
    joinedload(ProductionOrder.quotation).options(
        joinedload(Quotation.client),
        joinedload(Quotation.items),
    ),
)


def _calendar_entry(order: ProductionOrder) -> dict:
    quotation = order.quotation
    client = quotation.client if quotation else None
    items = list(quotation.items) if quotation and quotation.items else []
    return {
        "id": order.id,
        "quotation_id": order.quotation_id,
        "status": (order.status or "pendiente").lower(),
        "quotation_status": (quotation.status or "").lower() if quotation else "",
        "priority": order.priority or "media",
        "designer": order.designer or "",
        "fabricator": order.fabricator or "",
        "client_name": client.name if client and client.name else "Sin cliente",
        "first_item": items[0].detail if items else "",
        "extra_items": max(len(items) - 1, 0),
        "is_order": True,
        "detail_url": f"/production/{order.id}",
        "quotation_url": f"/quotations/{order.quotation_id}" if order.quotation_id else "",
    }


def _entry_matches_status_filter(entry: dict, status_filter: str) -> bool:
    if not status_filter:
        return True
    wanted = status_filter.lower().strip()
    if entry.get("status") == wanted:
        return True
    if entry.get("quotation_status") == wanted:
        return True
    return False


def _matches_calendar_view(entry_status: str, view: str) -> bool:
    if view == "upcoming" and entry_status in COMPLETED_ORDER_STATUSES:
        return False
    if view == "completed" and entry_status not in COMPLETED_ORDER_STATUSES:
        return False
    return True


def _production_query(db: Session):
    return production_orders_base_query(db).options(*_PRODUCTION_ORDER_LOAD)


# =========================================
# LISTADO PRODUCCIÓN
# =========================================

@router.get(
    "/",
    response_class=HTMLResponse
)
async def production_page(
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "produccion"]
    )

    if isinstance(user, RedirectResponse):
        return user

    prepare_production_module(db)

    orders = (
        _production_query(db)
        .order_by(ProductionOrder.delivery_date.asc())
        .all()
    )

    base = production_orders_base_query(db)
    active_orders_count = base.filter(
        ProductionOrder.status != "entregado"
    ).count()

    urgent_orders_count = base.filter(
        ProductionOrder.priority.in_(["alta", "urgente"])
    ).count()

    overdue_orders_count = base.filter(
        ProductionOrder.delivery_date != None,
        ProductionOrder.delivery_date < datetime.utcnow(),
        ProductionOrder.status != "entregado"
    ).count()

    return templates.TemplateResponse(
        request=request,
        name="production/list.html",
        context={
            "orders": orders,
            "active_orders_count": active_orders_count,
            "urgent_orders_count": urgent_orders_count,
            "overdue_orders_count": overdue_orders_count,
            "today": date.today(),
            "user": user,
        }
    )


# =========================================
# KANBAN
# =========================================
@router.get(
    "/kanban",
    response_class=HTMLResponse
)
async def production_kanban(
    request: Request,
    db: Session = Depends(get_db)
):
    user = role_required(request, ["admin", "produccion"])
    if isinstance(user, RedirectResponse):
        return user

    prepare_production_module(db)
    base = production_orders_base_query(db)

    all_orders = (
        _production_query(db)
        .order_by(ProductionOrder.id.asc())
        .all()
    )
    kanban_columns = build_kanban_columns(all_orders)
    grouped = group_orders_by_status(all_orders)

    active_orders_count = sum(
        col["count"]
        for col in kanban_columns
        if col["status"] != "entregado"
    )
    urgent_orders_count = base.filter(
        ProductionOrder.priority.in_(["alta", "urgente"])
    ).count()
    overdue_orders_count = base.filter(
        ProductionOrder.delivery_date != None,
        ProductionOrder.delivery_date < datetime.utcnow(),
        ProductionOrder.status != "entregado",
    ).count()

    view = request.query_params.get("view", "status")
    if view not in ("status", "week"):
        view = "status"
    hide_delivered = request.query_params.get("hide_delivered") == "1"
    today_date = date.today()
    anchor_week = parse_week_anchor(request.query_params.get("week", ""), today_date)
    prev_week = (anchor_week - timedelta(weeks=1)).strftime("%Y-%m-%d")
    next_week = (anchor_week + timedelta(weeks=1)).strftime("%Y-%m-%d")
    current_week = week_start(today_date).strftime("%Y-%m-%d")

    weekly_columns = build_kanban_week_columns(
        all_orders,
        anchor_week=anchor_week,
        today=today_date,
        hide_delivered=hide_delivered,
    )

    def kanban_url(**params):
        from urllib.parse import urlencode
        base_params = {
            "view": view,
            "week": anchor_week.strftime("%Y-%m-%d"),
        }
        if hide_delivered:
            base_params["hide_delivered"] = "1"
        base_params.update({k: v for k, v in params.items() if v not in (None, "")})
        return f"/production/kanban?{urlencode(base_params)}"

    return templates.TemplateResponse(
        request=request,
        name="production/kanban.html",
        context={
            "kanban_columns": kanban_columns,
            "weekly_columns": weekly_columns,
            "pending": grouped.get("pendiente", []),
            "designing": grouped.get("diseño", []),
            "producing": grouped.get("produccion", []),
            "packed": grouped.get("empacado", []),
            "shipped": grouped.get("enviado", []),
            "delivered": grouped.get("entregado", []),
            "active_orders_count": active_orders_count,
            "urgent_orders_count": urgent_orders_count,
            "overdue_orders_count": overdue_orders_count,
            "today": today_date,
            "user": user,
            "hide_delivered": hide_delivered,
            "view": view,
            "anchor_week": anchor_week,
            "week_param": anchor_week.strftime("%Y-%m-%d"),
            "prev_week_url": kanban_url(week=prev_week),
            "next_week_url": kanban_url(week=next_week),
            "current_week_url": kanban_url(week=current_week),
            "status_view_url": kanban_url(view="status"),
            "week_view_url": kanban_url(view="week"),
        }
    )

# =========================================
# CALENDARIO PRODUCCIÓN
# =========================================

def _parse_month(value: str) -> tuple[int, int] | None:
    try:
        year_str, month_str = value.split("-", 1)
        year, month = int(year_str), int(month_str)
        if 1 <= month <= 12:
            return year, month
    except (ValueError, AttributeError):
        pass
    return None


def _calendar_month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _as_calendar_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _calendar_date_in_scope(
    delivery: date,
    scope: str,
    month_start: date,
    month_end: date,
    start_date: str,
    end_date: str,
) -> bool:
    if scope != "month" and not start_date and not end_date:
        return True
    range_start = month_start
    range_end = month_end
    if start_date:
        try:
            range_start = max(range_start, datetime.strptime(start_date, "%Y-%m-%d").date())
        except ValueError:
            pass
    if end_date:
        try:
            range_end = min(range_end, datetime.strptime(end_date, "%Y-%m-%d").date())
        except ValueError:
            pass
    return range_start <= delivery <= range_end


def _filter_calendar_entries(
    entries: list[tuple[date, dict]],
    view: str,
    status: str,
    scope: str,
    month_start: date,
    month_end: date,
    start_date: str,
    end_date: str,
) -> list[tuple[date, dict]]:
    filtered: list[tuple[date, dict]] = []
    for delivery, entry in entries:
        if not _matches_calendar_view(entry["status"], view):
            continue
        if not _entry_matches_status_filter(entry, status):
            continue
        if not _calendar_date_in_scope(
            delivery, scope, month_start, month_end, start_date, end_date
        ):
            continue
        filtered.append((delivery, entry))
    return filtered


@router.get(
    "/calendar",
    response_class=HTMLResponse
)
async def production_calendar(
    request: Request,
    db: Session = Depends(get_db)
):
    user = role_required(request, ["admin", "produccion"])
    if isinstance(user, RedirectResponse):
        return user

    prepare_production_module(db)

    sync_candidates = (
        db.query(Quotation)
        .filter(
            Quotation.delivery_date.isnot(None),
            Quotation.status.in_(["aprobada", "produccion"]),
        )
        .all()
    )
    for quotation in sync_candidates:
        ensure_production_order(db, quotation)
    if sync_candidates:
        db.commit()

    view: str = request.query_params.get("view", "upcoming")
    status: str = request.query_params.get("status", "")
    start_date: str = request.query_params.get("start_date", "")
    end_date: str = request.query_params.get("end_date", "")
    month_param: str = request.query_params.get("month", "")
    scope: str = request.query_params.get("scope", "all")

    today_date = date.today()
    parsed_month = _parse_month(month_param)
    if parsed_month:
        cal_year, cal_month = parsed_month
    else:
        cal_year, cal_month = today_date.year, today_date.month

    month_start, month_end = _calendar_month_bounds(cal_year, cal_month)
    if cal_month == 1:
        prev_year, prev_mon = cal_year - 1, 12
    else:
        prev_year, prev_mon = cal_year, cal_month - 1
    if cal_month == 12:
        next_year, next_mon = cal_year + 1, 1
    else:
        next_year, next_mon = cal_year, cal_month + 1

    orders = (
        _production_query(db)
        .order_by(ProductionOrder.id.asc())
        .all()
    )

    all_entries: list[tuple[date, dict]] = []
    for order in orders:
        delivery = _as_calendar_date(order_delivery_date(order))
        if not delivery:
            continue
        all_entries.append((delivery, _calendar_entry(order)))

    scoped_entries = [
        (delivery, entry)
        for delivery, entry in all_entries
        if _calendar_date_in_scope(
            delivery, scope, month_start, month_end, start_date, end_date
        )
        and _entry_matches_status_filter(entry, status)
    ]

    filtered = _filter_calendar_entries(
        all_entries, view, status, scope, month_start, month_end, start_date, end_date
    )
    filtered.sort(key=lambda row: (row[0], row[1]["id"]))

    grouped_orders: dict[date, list[dict]] = defaultdict(list)
    for delivery, entry in filtered:
        grouped_orders[delivery].append(entry)

    grouped_days = [
        {"date": delivery, "orders": grouped_orders[delivery]}
        for delivery in sorted(grouped_orders.keys())
    ]

    active_in_scope = [
        (d, e)
        for d, e in scoped_entries
        if not _matches_calendar_view(e["status"], "completed")
    ]
    active_dates = [d for d, _ in active_in_scope]
    overdue_count = sum(1 for d in active_dates if d < today_date)
    today_count = sum(1 for d in active_dates if d == today_date)
    upcoming_count = len(active_in_scope)
    completed_count = sum(
        1
        for _, entry in scoped_entries
        if _matches_calendar_view(entry["status"], "completed")
    )
    upcoming_tab_count = sum(
        1
        for _, entry in scoped_entries
        if _matches_calendar_view(entry["status"], "upcoming")
    )
    completed_tab_count = sum(
        1
        for _, entry in scoped_entries
        if _matches_calendar_view(entry["status"], "completed")
    )
    all_tab_count = len(scoped_entries)
    month_count = len(filtered)
    filters_active = bool(status or start_date or end_date or scope == "month")

    month_names = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]

    def build_calendar_url(**overrides):
        params = {
            "view": view,
            "scope": scope,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "month": month_param or f"{cal_year:04d}-{cal_month:02d}",
        }
        params.update(overrides)
        clean = {k: v for k, v in params.items() if v not in (None, "")}
        from urllib.parse import urlencode
        qs = urlencode(clean)
        return f"/production/calendar?{qs}" if qs else "/production/calendar"

    return templates.TemplateResponse(
        request=request,
        name="production/calendar.html",
        context={
            "grouped_orders": dict(grouped_orders),
            "grouped_days": grouped_days,
            "today": today_date,
            "view": view,
            "scope": scope,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "month_param": month_param or f"{cal_year:04d}-{cal_month:02d}",
            "cal_year": cal_year,
            "cal_month": cal_month,
            "month_label": f"{month_names[cal_month]} {cal_year}",
            "prev_month_url": build_calendar_url(month=f"{prev_year:04d}-{prev_mon:02d}"),
            "next_month_url": build_calendar_url(month=f"{next_year:04d}-{next_mon:02d}"),
            "current_month_url": build_calendar_url(
                month=f"{today_date.year:04d}-{today_date.month:02d}",
                scope="month",
            ),
            "month_scope_url": build_calendar_url(
                scope="month",
                month=f"{today_date.year:04d}-{today_date.month:02d}",
            ),
            "all_dates_url": build_calendar_url(scope="all"),
            "clear_filters_url": "/production/calendar?view=upcoming&scope=all",
            "upcoming_count": upcoming_count,
            "completed_count": completed_count,
            "upcoming_tab_count": upcoming_tab_count,
            "completed_tab_count": completed_tab_count,
            "all_tab_count": all_tab_count,
            "overdue_count": overdue_count,
            "today_count": today_count,
            "month_count": month_count,
            "filters_active": filters_active,
            "user": user,
        }
    )

# =========================================
# CAMBIO DE ESTADO
# =========================================

@router.get("/move/{order_id}/{status}")
async def move_order(
    request: Request,
    order_id: int,
    status: str,
    db: Session = Depends(get_db)
):

    user = role_required(request, ["admin", "produccion"])
    if isinstance(user, RedirectResponse):
        return user

    order = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.id == order_id
    ).first()

    if not order:
        return RedirectResponse(url="/production/kanban", status_code=302)

    error = validate_production_status_change(order, status)
    if error:
        return error

    error = validate_shipment_for_sent(order, status, db)
    if error:
        return error

    apply_production_status_change(order, status, db)

    db.commit()

    return_to = request.query_params.get("return", "")
    view = request.query_params.get("view", "")
    week = request.query_params.get("week", "")
    if return_to == "kanban":
        from urllib.parse import urlencode
        params = {k: v for k, v in {"view": view, "week": week}.items() if v}
        redirect_url = f"/production/kanban?{urlencode(params)}" if params else "/production/kanban"
    elif user.role == "produccion":
        redirect_url = "/production/"
    else:
        redirect_url = "/production/kanban"
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/{order_id}/advance")
async def advance_production_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
):
    user = role_required(request, ["admin", "produccion"])
    if isinstance(user, RedirectResponse):
        return user

    order = db.query(ProductionOrder).filter(ProductionOrder.id == order_id).first()
    if not order:
        return RedirectResponse(url="/production/", status_code=302)

    next_status = next_production_status(order.status)
    if not next_status:
        return RedirectResponse(url=f"/production/{order_id}", status_code=302)

    error = validate_production_status_change(order, next_status)
    if error:
        return error

    error = validate_shipment_for_sent(order, next_status, db)
    if error:
        return error

    apply_production_status_change(order, next_status, db)
    db.commit()

    return RedirectResponse(
        url=f"/production/{order_id}?saved=1",
        status_code=302,
    )
# =========================================
# ACTUALIZAR ORDEN
# =========================================

@router.post(
    "/{order_id}/update/"
)
async def update_production(
    request: Request,
    order_id: int,
    designer: str = Form(""),
    fabricator: str = Form(""),
    priority: str = Form("media"),
    observations: str = Form(""),
    status: str = Form("pendiente"),
    delivery_date: str = Form(""),
    db: Session = Depends(get_db)
):

    user = role_required(request, ["admin", "produccion"])
    if isinstance(user, RedirectResponse):
        return user

    order = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.id == order_id
    ).first()

    if not order:
        return RedirectResponse(url="/production/", status_code=302)

    order.designer = designer.strip()
    order.fabricator = fabricator.strip()

    error = validate_production_status_change(order, status)
    if error:
        return error

    error = validate_shipment_for_sent(order, status, db)
    if error:
        return error

    order.priority = priority
    order.observations = observations

    if delivery_date:
        try:
            parsed = datetime.strptime(delivery_date, "%Y-%m-%d").date()
            order.delivery_date = datetime.combine(parsed, time.min)
            if order.quotation and order.quotation.delivery_date != parsed:
                order.quotation.delivery_date = parsed
        except ValueError:
            pass

    apply_production_status_change(order, status, db)

    db.commit()

    return RedirectResponse(
        url=f"/production/{order_id}?saved=1",
        status_code=302
    )


# =========================================
# DETALLE ORDEN
# =========================================

def _production_detail_context(order, request, shipment, user) -> dict:
    current_status = (order.status or "pendiente").lower()
    next_status = next_production_status(current_status)
    return {
        "order": order,
        "shipment": shipment,
        "user": user,
        "production_stages": PRODUCTION_ORDER_STATUSES,
        "status_labels": PRODUCTION_STATUS_LABELS,
        "current_status_index": production_status_index(current_status),
        "next_status": next_status,
        "next_status_label": PRODUCTION_STATUS_LABELS.get(next_status or "", ""),
        "next_status_hint": status_requirements_hint(next_status or ""),
        "delivery_meta": production_order_delivery_meta(order),
        "saved": request.query_params.get("saved") == "1",
    }


@router.get(
    "/{order_id}",
    response_class=HTMLResponse
)
async def production_detail(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "produccion"]
    )

    if isinstance(user, RedirectResponse):
        return user

    prepare_production_module(db)

    order = (
        _production_query(db)
        .filter(ProductionOrder.id == order_id)
        .first()
    )

    if not order or not quotation_visible_in_production(order.quotation):
        return RedirectResponse(url="/production/", status_code=302)

    if not order.delivery_date and order.quotation and order.quotation.delivery_date:
        qd = order.quotation.delivery_date
        if isinstance(qd, datetime):
            order.delivery_date = qd
        else:
            order.delivery_date = datetime.combine(qd, time.min)
        db.commit()

    shipment = (
        db.query(Shipment)
        .filter(Shipment.quotation_id == order.quotation_id)
        .order_by(Shipment.id.desc())
        .first()
    )

    return templates.TemplateResponse(
        request=request,
        name="production/detail.html",
        context=_production_detail_context(order, request, shipment, user),
    )
