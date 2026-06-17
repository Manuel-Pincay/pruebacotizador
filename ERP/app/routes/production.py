from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from datetime import date, datetime, time, timedelta
from calendar import monthrange
from collections import defaultdict

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import JSONResponse

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
from app.services.logo_types import register_logo_template_globals
from app.services.production_order_service import (
    DESIGN_MATERIALS,
    DESIGN_SIZES,
    USB_REFERENCES,
    PRODUCTION_ORDER_STATUSES,
    PRODUCTION_STATUS_SEQUENCE,
    approve_design,
    build_history_list,
    build_order_dict,
    export_design_sheet_pdf,
    fabrication_data_complete,
    get_production_order,
    normalize_status,
    update_design_fields,
    list_assignable_designers,
    list_assignable_fabricators,
    resolve_selected_designer_id,
    resolve_selected_fabricator_id,
    apply_designer_assignment,
    apply_fabricator_assignment,
)
from app.services.kanban_service import (
    KPI_KEYS,
    build_kanban_table_rows,
    build_status_kanban_board,
    compute_kanban_kpis,
    filter_orders,
    filter_orders_by_week,
    get_order_panel_detail,
    list_filter_options,
    load_kanban_orders,
    monday_to_week_input,
    parse_kanban_week,
    validate_kanban_move,
    week_header_label,
)
from app.auth.design_permissions import can_edit_design_order, can_view_design_order

PRODUCTION_DETAIL_ROLES = ["admin", "produccion", "disenador"]

router = APIRouter(
    prefix="/production",
    tags=["production"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config
register_logo_template_globals(templates.env)

_PRODUCTION_ORDER_LOAD = (
    joinedload(ProductionOrder.quotation).options(
        joinedload(Quotation.client),
        joinedload(Quotation.items),
    ),
)

LIST_COMPLETED_STATUSES = frozenset({"entregado", "cancelado", "envio"})


def _order_is_list_completed(status: str | None) -> bool:
    return normalize_status(status) in LIST_COMPLETED_STATUSES


def _filter_production_list(
    orders: list[ProductionOrder],
    *,
    view: str,
    status: str,
) -> list[ProductionOrder]:
    view = (view or "active").lower().strip()
    status_filter = normalize_status(status) if status else ""

    filtered: list[ProductionOrder] = []
    for order in orders:
        normalized = normalize_status(order.status)
        is_completed = normalized in LIST_COMPLETED_STATUSES

        if view == "completed" and not is_completed:
            continue
        if view == "active" and is_completed:
            continue
        if status_filter and normalized != status_filter:
            continue
        filtered.append(order)
    return filtered


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
    db: Session = Depends(get_db),
    view: str = "active",
    status: str = "",
):

    user = role_required(
        request,
        ["admin", "produccion"]
    )

    if isinstance(user, RedirectResponse):
        return user

    prepare_production_module(db)

    all_orders = (
        _production_query(db)
        .order_by(ProductionOrder.created_at.desc(), ProductionOrder.id.desc())
        .all()
    )

    view = (view or "active").lower().strip()
    if view not in {"active", "completed"}:
        view = "active"

    orders = _filter_production_list(all_orders, view=view, status=status)
    active_tab_count = sum(1 for order in all_orders if not _order_is_list_completed(order.status))
    completed_tab_count = sum(1 for order in all_orders if _order_is_list_completed(order.status))

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

    status_filter = normalize_status(status) if status else ""
    status_filter_label = PRODUCTION_STATUS_LABELS.get(status_filter, "") if status_filter else ""

    return templates.TemplateResponse(
        request=request,
        name="production/list.html",
        context={
            "orders": orders,
            "active_orders_count": active_orders_count,
            "urgent_orders_count": urgent_orders_count,
            "overdue_orders_count": overdue_orders_count,
            "active_tab_count": active_tab_count,
            "completed_tab_count": completed_tab_count,
            "filters": {
                "view": view,
                "status": status_filter,
                "status_label": status_filter_label,
            },
            "status_options": PRODUCTION_ORDER_STATUSES,
            "today": date.today(),
            "user": user,
        }
    )


# =========================================
# KANBAN (planificación semanal + tabla)
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
    today_date = date.today()
    params = request.query_params

    mode = params.get("mode", "kanban")
    if mode not in ("table", "kanban"):
        mode = "table"

    hide_delivered = params.get("hide_delivered", "1") != "0"
    month = params.get("month", "")
    client_id_raw = params.get("client_id", "")
    client_id = int(client_id_raw) if client_id_raw.isdigit() else None
    designer = params.get("designer", "").strip()
    status_filter = params.get("status", "").strip()
    material = params.get("material", "").strip()
    custom_only = params.get("custom", "") == "1"

    all_orders = load_kanban_orders(db)
    filtered = filter_orders(
        all_orders,
        today=today_date,
        month=month,
        client_id=client_id,
        designer=designer,
        status=status_filter,
        material=material,
        custom_only=custom_only,
        hide_delivered=hide_delivered if mode == "table" else False,
    )

    selected_week = parse_kanban_week(params.get("week", ""), today_date)
    week_title, week_sublabel, week_number = week_header_label(selected_week, today_date)
    week_input_value = monday_to_week_input(selected_week)
    prev_week = monday_to_week_input(selected_week - timedelta(weeks=1))
    next_week = monday_to_week_input(selected_week + timedelta(weeks=1))

    kanban_orders = filter_orders_by_week(filtered, selected_week) if mode == "kanban" else filtered

    kpis = compute_kanban_kpis(kanban_orders if mode == "kanban" else filtered, today_date)
    status_board = build_status_kanban_board(kanban_orders, today=today_date)
    table_rows = build_kanban_table_rows(filtered, today_date)
    filter_options = list_filter_options(db, all_orders)

    def kanban_url(**extra):
        from urllib.parse import urlencode
        base = {
            "mode": extra.pop("mode", mode),
            "hide_delivered": "0" if not hide_delivered else "1",
            "week": extra.pop("week", week_input_value),
        }
        if month:
            base["month"] = month
        if client_id:
            base["client_id"] = str(client_id)
        if designer:
            base["designer"] = designer
        if status_filter:
            base["status"] = status_filter
        if material:
            base["material"] = material
        if custom_only:
            base["custom"] = "1"
        base.update({k: v for k, v in extra.items() if v not in (None, "")})
        return f"/production/kanban?{urlencode(base)}"

    return templates.TemplateResponse(
        request=request,
        name="production/kanban.html",
        context={
            "user": user,
            "mode": mode,
            "today": today_date,
            "kpis": kpis,
            "kpi_labels": dict(KPI_KEYS),
            "status_board": status_board,
            "table_rows": table_rows,
            "total_count": len(kanban_orders if mode == "kanban" else filtered),
            "selected_week": selected_week,
            "week_title": week_title,
            "week_sublabel": week_sublabel,
            "week_number": week_number,
            "week_input_value": week_input_value,
            "prev_week_url": kanban_url(mode=mode, week=prev_week),
            "next_week_url": kanban_url(mode=mode, week=next_week),
            "current_week_url": kanban_url(mode=mode, week=monday_to_week_input(today_date)),
            "filter_options": filter_options,
            "filters": {
                "month": month,
                "client_id": client_id,
                "designer": designer,
                "status": status_filter,
                "material": material,
                "custom_only": custom_only,
                "hide_delivered": hide_delivered,
            },
            "table_view_url": kanban_url(mode="table"),
            "kanban_view_url": kanban_url(mode="kanban"),
            "clear_filters_url": kanban_url(
                mode=mode, month="", client_id="", designer="", status="", material="", custom=""
            ),
        },
    )


@router.get("/kanban/orders/{order_id}/panel")
async def kanban_order_panel(order_id: int, request: Request, db: Session = Depends(get_db)):
    user = role_required(request, ["admin", "produccion"])
    if isinstance(user, RedirectResponse):
        return user

    detail = get_order_panel_detail(db, order_id)
    if not detail:
        return JSONResponse(status_code=404, content={"error": "Orden no encontrada."})
    return detail


@router.post("/kanban/orders/{order_id}/move")
async def kanban_order_move(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = role_required(request, ["admin", "produccion"])
    if isinstance(user, RedirectResponse):
        return user

    body = await request.json()
    target_status = (body.get("status") or "").strip()
    if not target_status:
        return JSONResponse(status_code=400, content={"success": False, "message": "Estado requerido."})

    order = (
        _production_query(db)
        .filter(ProductionOrder.id == order_id)
        .first()
    )
    if not order:
        return JSONResponse(status_code=404, content={"success": False, "message": "Orden no encontrada."})

    error = validate_kanban_move(order, target_status)
    if error:
        return JSONResponse(status_code=400, content={"success": False, "message": error})

    if normalize_status(target_status) == "envio":
        shipment_error = validate_shipment_for_sent(order, target_status, db)
        if shipment_error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Requiere guía de envío creada."},
            )

    apply_production_status_change(order, target_status, db)
    db.commit()

    return {
        "success": True,
        "status": normalize_status(order.status),
        "status_label": PRODUCTION_STATUS_LABELS.get(normalize_status(order.status), order.status),
    }

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
    designer_user_id: str = Form(""),
    fabricator_user_id: str = Form(""),
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

    parsed_designer_id = int(designer_user_id) if designer_user_id.strip().isdigit() else None
    parsed_fabricator_id = int(fabricator_user_id) if fabricator_user_id.strip().isdigit() else None
    apply_designer_assignment(order, db, parsed_designer_id)
    apply_fabricator_assignment(order, db, parsed_fabricator_id)

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


@router.post("/{order_id}/fabrication/")
async def save_fabrication(
    order_id: int,
    request: Request,
    file_name: str = Form(""),
    material: str = Form(""),
    size: str = Form(""),
    usb_reference: str = Form(""),
    detail: str = Form(""),
    copies: int = Form(1),
    action: str = Form("save"),
    db: Session = Depends(get_db),
):
    user = role_required(request, PRODUCTION_DETAIL_ROLES)
    if isinstance(user, RedirectResponse):
        return user

    order = db.query(ProductionOrder).filter(ProductionOrder.id == order_id).first()
    if not order:
        return RedirectResponse(url="/production/", status_code=302)

    if user.role == "disenador" and not can_edit_design_order(user, order):
        return RedirectResponse(url=f"/production/{order_id}", status_code=302)

    try:
        update_design_fields(
            db,
            order,
            file_name=file_name,
            material=material,
            size=size,
            usb_reference=usb_reference,
            notes=detail,
            copies=copies,
            user=user,
        )
        if action == "approve":
            order = get_production_order(db, order_id) or order
            approve_design(db, order, user=user)
    except ValueError as exc:
        from urllib.parse import quote
        return RedirectResponse(
            url=f"/production/{order_id}?fab_error={quote(str(exc))}",
            status_code=302,
        )

    return RedirectResponse(url=f"/production/{order_id}?saved=1", status_code=302)


@router.get("/{order_id}/fabrication/print")
async def print_fabrication(order_id: int, request: Request, db: Session = Depends(get_db)):
    user = role_required(request, PRODUCTION_DETAIL_ROLES)
    if isinstance(user, RedirectResponse):
        return user

    order = get_production_order(db, order_id)
    if not order:
        return RedirectResponse(url="/production/", status_code=302)
    if user.role == "disenador" and not can_view_design_order(user, order):
        return RedirectResponse(url="/production/", status_code=302)

    client = order.quotation.client if order.quotation else None
    data = build_order_dict(order, client_name=client.name if client else "—")
    from fastapi.responses import StreamingResponse
    pdf = export_design_sheet_pdf(data)
    return StreamingResponse(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="fabricacion_OP-{order_id:04d}.pdf"'},
    )


# =========================================
# DETALLE ORDEN
# =========================================

def _production_detail_context(order, request, shipment, user, db) -> dict:
    current_status = normalize_status(order.status)
    next_status = next_production_status(current_status)
    po = get_production_order(db, order.id) if order and order.id else order
    fab = build_order_dict(po or order) if order else {}
    can_edit_fab = (
        user.role in {"admin", "disenador"}
        and current_status in {"pendiente", "diseno"}
        and (user.role == "admin" or can_edit_design_order(user, order))
    )
    can_manage_order = user.role in {"admin", "produccion"}
    designers = list_assignable_designers(db)
    fabricators = list_assignable_fabricators(db)
    return {
        "order": order,
        "shipment": shipment,
        "user": user,
        "designers": designers,
        "fabricators": fabricators,
        "selected_designer_id": resolve_selected_designer_id(order, db) if order else None,
        "selected_fabricator_id": resolve_selected_fabricator_id(order, db) if order else None,
        "current_status": current_status,
        "production_stages": PRODUCTION_STATUS_SEQUENCE,
        "status_labels": PRODUCTION_STATUS_LABELS,
        "current_status_index": production_status_index(current_status),
        "next_status": next_status if can_manage_order else None,
        "next_status_label": PRODUCTION_STATUS_LABELS.get(next_status or "", ""),
        "next_status_hint": status_requirements_hint(next_status or ""),
        "delivery_meta": production_order_delivery_meta(order),
        "saved": request.query_params.get("saved") == "1",
        "fabrication": fab,
        "fabrication_complete": fabrication_data_complete(order),
        "can_edit_fabrication": can_edit_fab,
        "can_manage_order": can_manage_order,
        "materials": DESIGN_MATERIALS,
        "sizes": DESIGN_SIZES,
        "usb_references": USB_REFERENCES,
        "history": build_history_list(po) if po else [],
        "fab_error": request.query_params.get("fab_error", ""),
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
        PRODUCTION_DETAIL_ROLES
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

    if user.role == "disenador" and not can_view_design_order(user, order):
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
        context=_production_detail_context(order, request, shipment, user, db),
    )
