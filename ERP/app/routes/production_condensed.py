from datetime import date
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.auth_handler import role_required
from app.config.settings import settings
from app.database import get_db
from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.services.condensed_service import (
    TRACKING_STATUSES,
    TRACKING_STATUS_COLORS,
    TRACKING_STATUS_LABELS,
    compute_kpis,
    export_condensed_excel,
    export_condensed_pdf,
    flatten_order_groups,
    get_filtered_order_groups,
    get_order_detail,
    paginate_order_groups,
    update_quotation_tracking_status,
)
from app.utils.context import get_global_config
from app.utils.image_storage import design_image_url
from app.utils.pagination import build_page_url

router = APIRouter(prefix="/production", tags=["production-condensed"])

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["build_page_url"] = build_page_url
templates.env.globals["design_image_url"] = design_image_url
templates.env.globals["tracking_status_colors"] = TRACKING_STATUS_COLORS

CONDENSED_ROLES = ["admin", "ventas", "disenador"]
CONDENSED_WRITE_ROLES = ["admin", "ventas"]


def _require_condensed_write(request: Request):
    user = role_required(request, CONDENSED_WRITE_ROLES)
    if isinstance(user, RedirectResponse):
        return user
    return user


def _require_condensed_access(request: Request):
    user = role_required(request, CONDENSED_ROLES)
    if isinstance(user, RedirectResponse):
        return user
    return user


def _parse_filters(
    *,
    month: str = "",
    year: str = "",
    client_id: str = "",
    production_status: str = "",
    custom_filter: str = "",
    search: str = "",
    group_by: str = "order",
    date_basis: str = "delivery",
    apply_current_month_default: bool = False,
):
    today = date.today()
    parsed_month = int(month) if month.strip().isdigit() else None
    parsed_year = int(year) if year.strip().isdigit() else None

    if apply_current_month_default and parsed_month is None and parsed_year is None:
        parsed_month = today.month
        parsed_year = today.year
    elif parsed_month and not parsed_year:
        parsed_year = today.year

    parsed_client = int(client_id) if client_id.strip().isdigit() else None

    return {
        "month": parsed_month,
        "year": parsed_year,
        "client_id": parsed_client,
        "production_status": production_status.strip(),
        "custom_filter": custom_filter.strip(),
        "search": search.strip(),
        "group_by": group_by if group_by in {"order", "delivery", "client", "product"} else "order",
        "date_basis": date_basis if date_basis in {"delivery", "quotation"} else "delivery",
    }


def _filter_params(filters: dict, page: int = 1) -> dict:
    return {
        "month": filters["month"] or "",
        "year": filters["year"] or "",
        "client_id": filters["client_id"] or "",
        "production_status": filters["production_status"],
        "custom_filter": filters["custom_filter"],
        "search": filters["search"],
        "group_by": filters["group_by"],
        "date_basis": filters["date_basis"],
        "page": page,
    }


def _active_filter_labels(filters: dict, clients: list) -> list[str]:
    labels: list[str] = []
    month_names = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }

    if filters.get("month") or filters.get("year"):
        basis = "entrega" if filters.get("date_basis") == "delivery" else "cotización"
        if filters.get("month") and filters.get("year"):
            labels.append(
                f"{month_names.get(filters['month'], filters['month'])} {filters['year']} ({basis})"
            )
        elif filters.get("year"):
            labels.append(f"Año {filters['year']} ({basis})")
        elif filters.get("month"):
            labels.append(f"{month_names.get(filters['month'], filters['month'])} ({basis})")

    if filters.get("client_id"):
        client_name = next(
            (client.name for client in clients if client.id == filters["client_id"]),
            f"Cliente #{filters['client_id']}",
        )
        labels.append(f"Cliente: {client_name}")

    if filters.get("production_status"):
        labels.append(
            "Estado: "
            + TRACKING_STATUS_LABELS.get(
                filters["production_status"],
                filters["production_status"],
            )
        )

    if filters.get("custom_filter") == "yes":
        labels.append("Con personalizados")
    elif filters.get("custom_filter") == "no":
        labels.append("Solo catálogo")

    if filters.get("search"):
        labels.append(f'Búsqueda: "{filters["search"]}"')

    group_labels = {
        "order": "Orden de cotización",
        "delivery": "Fecha de entrega",
        "client": "Cliente",
        "product": "Producto",
    }
    if filters.get("group_by") and filters.get("group_by") != "order":
        labels.append(f"Ordenado por: {group_labels.get(filters['group_by'], filters['group_by'])}")

    return labels


def _fetch_order_groups(db: Session, filters: dict, page: int, per_page: int):
    all_groups = get_filtered_order_groups(db, **filters)
    pagination = paginate_order_groups(all_groups, page, per_page)
    return pagination["items"], pagination


def _fetch_all_order_groups(db: Session, filters: dict):
    return get_filtered_order_groups(db, **filters)


@router.get("/condensed", response_class=HTMLResponse)
async def production_condensed_page(
    request: Request,
    month: str = "",
    year: str = "",
    client_id: str = "",
    production_status: str = "",
    custom_filter: str = "",
    search: str = "",
    group_by: str = "order",
    date_basis: str = "delivery",
    page: int = 1,
    db: Session = Depends(get_db),
):
    user = _require_condensed_access(request)
    if isinstance(user, RedirectResponse):
        return user

    query = request.query_params
    apply_current_month_default = "month" not in query and "year" not in query

    filters = _parse_filters(
        month=month,
        year=year,
        client_id=client_id,
        production_status=production_status,
        custom_filter=custom_filter,
        search=search,
        group_by=group_by,
        date_basis=date_basis,
        apply_current_month_default=apply_current_month_default,
    )

    rows, pagination = _fetch_order_groups(db, filters, page, settings.per_page)
    kpis = compute_kpis(db, **filters)
    clients = db.query(Client).order_by(Client.name).all()
    active_filters = _active_filter_labels(filters, clients)
    export_params = {
        k: v for k, v in _filter_params(filters).items()
        if k != "page" and v not in (None, "")
    }
    export_query = urlencode(export_params)

    return templates.TemplateResponse(
        request=request,
        name="production/condensed.html",
        context={
            "user": user,
            "order_groups": rows,
            "pagination": pagination,
            "kpis": kpis,
            "clients": clients,
            "filters": filters,
            "active_filters": active_filters,
            "filter_params": _filter_params(filters, pagination["page"]),
            "export_query": export_query,
            "tracking_statuses": TRACKING_STATUSES,
            "tracking_status_labels": TRACKING_STATUS_LABELS,
            "today": __import__("datetime").date.today(),
        },
    )


@router.get("/condensed/orders/{quotation_id}/detail")
async def condensed_order_detail(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_condensed_access(request)
    if isinstance(user, RedirectResponse):
        return user

    detail = get_order_detail(db, quotation_id)
    if not detail:
        return JSONResponse(status_code=404, content={"message": "Orden no encontrada."})

    return detail


@router.post("/condensed/orders/{quotation_id}/status")
async def condensed_update_order_status(
    quotation_id: int,
    request: Request,
    status: str = Form(...),
    notes: str = Form(""),
    assigned_to: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _require_condensed_write(request)
    if isinstance(user, RedirectResponse):
        return user

    try:
        tracking = update_quotation_tracking_status(
            db,
            quotation_id,
            status=status,
            notes=notes,
            assigned_to=assigned_to,
        )
        return {
            "success": True,
            "status": tracking.status,
            "status_label": TRACKING_STATUS_LABELS.get(tracking.status, tracking.status),
        }
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})


@router.get("/condensed/export/excel")
async def condensed_export_excel(
    request: Request,
    month: str = "",
    year: str = "",
    client_id: str = "",
    production_status: str = "",
    custom_filter: str = "",
    search: str = "",
    group_by: str = "order",
    date_basis: str = "delivery",
    db: Session = Depends(get_db),
):
    user = _require_condensed_write(request)
    if isinstance(user, RedirectResponse):
        return user

    filters = _parse_filters(
        month=month,
        year=year,
        client_id=client_id,
        production_status=production_status,
        custom_filter=custom_filter,
        search=search,
        group_by=group_by,
        date_basis=date_basis,
        apply_current_month_default=True,
    )
    order_groups = _fetch_all_order_groups(db, filters)
    rows = flatten_order_groups(order_groups)
    buffer = export_condensed_excel(rows)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="condensado_produccion.xlsx"'},
    )


@router.get("/condensed/export/pdf")
async def condensed_export_pdf(
    request: Request,
    month: str = "",
    year: str = "",
    client_id: str = "",
    production_status: str = "",
    custom_filter: str = "",
    search: str = "",
    group_by: str = "order",
    date_basis: str = "delivery",
    db: Session = Depends(get_db),
):
    user = _require_condensed_write(request)
    if isinstance(user, RedirectResponse):
        return user

    filters = _parse_filters(
        month=month,
        year=year,
        client_id=client_id,
        production_status=production_status,
        custom_filter=custom_filter,
        search=search,
        group_by=group_by,
        date_basis=date_basis,
        apply_current_month_default=True,
    )
    order_groups = _fetch_all_order_groups(db, filters)
    rows = flatten_order_groups(order_groups)
    config = db.query(CompanyConfig).first()
    clients = db.query(Client).order_by(Client.name).all()
    issued_by = user.full_name or user.username if user else "Sistema ERP"

    month_part = ""
    if filters.get("year"):
        month_part = f"_{filters['year']:04d}"
        if filters.get("month"):
            month_part = f"_{filters['year']:04d}-{filters['month']:02d}"

    buffer = export_condensed_pdf(
        rows,
        config=config,
        filters=filters,
        clients=clients,
        issued_by=issued_by,
    )

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="condensado_produccion{month_part}.pdf"'
            )
        },
    )
