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
from app.services.condensed_service import TRACKING_STATUSES, TRACKING_STATUS_COLORS, TRACKING_STATUS_LABELS
from app.services.fabrication_condensed_service import (
    active_filter_labels,
    compute_fabrication_kpis,
    export_fabrication_excel,
    export_fabrication_pdf,
    fabricator_mark_completed,
    fabricator_mark_taken,
    get_fabrication_order_detail,
    get_fabrication_order_groups,
    parse_fabrication_filters,
)
from app.services.condensed_service import paginate_order_groups
from app.services.production_helpers import prepare_production_module
from app.utils.context import get_global_config
from app.utils.image_storage import design_image_url
from app.utils.pagination import build_page_url

router = APIRouter(prefix="/production", tags=["fabrication-condensed"])

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["build_page_url"] = build_page_url
templates.env.globals["design_image_url"] = design_image_url
templates.env.globals["tracking_status_colors"] = TRACKING_STATUS_COLORS

FABRICATION_CONDENSED_ROLES = ["admin", "ventas", "disenador", "produccion"]


def _require_access(request: Request):
    user = role_required(request, FABRICATION_CONDENSED_ROLES)
    if isinstance(user, RedirectResponse):
        return user
    return user


def _can_fabricator_actions(user) -> bool:
    return getattr(user, "role", "") in {"admin", "produccion"}


def _restore_order_labels(groups: list[dict]) -> None:
    for group in groups:
        order_id = group.get("production_order_id")
        if not order_id:
            continue
        label = f"OP-{order_id:04d}"
        group["order_label"] = label
        for product in group.get("products") or []:
            product["order_label"] = label


def _filter_params(filters: dict, page: int = 1) -> dict:
    params = {
        "month": filters.get("month") or "",
        "year": filters.get("year") or "",
        "client_id": filters.get("client_id") or "",
        "production_status": filters.get("production_status") or "",
        "custom_filter": filters.get("custom_filter") or "",
        "search": filters.get("search") or "",
        "group_by": filters.get("group_by") or "order",
        "page": page,
    }
    if filters.get("show_completed"):
        params["show_completed"] = "1"
    return params


def _fetch_groups(db: Session, filters: dict, page: int, per_page: int):
    all_groups = get_fabrication_order_groups(db, **filters)
    pagination = paginate_order_groups(all_groups, page, per_page)
    _restore_order_labels(pagination["items"])
    return pagination["items"], pagination


@router.get("/fabrication-condensed", response_class=HTMLResponse)
async def fabrication_condensed_page(
    request: Request,
    month: str = "",
    year: str = "",
    client_id: str = "",
    production_status: str = "",
    custom_filter: str = "",
    search: str = "",
    group_by: str = "order",
    show_completed: str = "",
    page: int = 1,
    db: Session = Depends(get_db),
):
    user = _require_access(request)
    if isinstance(user, RedirectResponse):
        return user

    prepare_production_module(db)
    query = request.query_params
    apply_default = "month" not in query and "year" not in query

    filters = parse_fabrication_filters(
        month=month,
        year=year,
        client_id=client_id,
        production_status=production_status,
        custom_filter=custom_filter,
        search=search,
        group_by=group_by,
        show_completed=show_completed,
        apply_current_month_default=apply_default,
    )

    all_groups = get_fabrication_order_groups(db, **filters)
    rows, pagination = _fetch_groups(db, filters, page, settings.per_page)
    kpis = compute_fabrication_kpis(all_groups)
    clients = db.query(Client).order_by(Client.name).all()
    active_filters = active_filter_labels(filters, clients)
    export_params = {
        k: v for k, v in _filter_params(filters).items()
        if k != "page" and v not in (None, "")
    }
    export_query = urlencode(export_params)

    return templates.TemplateResponse(
        request=request,
        name="production/fabrication_condensed.html",
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
            "can_fabricator_actions": _can_fabricator_actions(user),
            "today": date.today(),
        },
    )


@router.get("/fabrication-condensed/orders/{quotation_id}/detail")
async def fabrication_condensed_order_detail(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_access(request)
    if isinstance(user, RedirectResponse):
        return user

    detail = get_fabrication_order_detail(db, quotation_id)
    if not detail:
        return JSONResponse(status_code=404, content={"message": "Orden no encontrada."})

    return detail


@router.post("/fabrication-condensed/orders/{order_id}/action")
async def fabrication_condensed_order_action(
    order_id: int,
    request: Request,
    action: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _require_access(request)
    if isinstance(user, RedirectResponse):
        return user

    if not _can_fabricator_actions(user):
        return JSONResponse(status_code=403, content={"success": False, "message": "No autorizado."})

    prepare_production_module(db)
    action_code = (action or "").strip().lower()

    try:
        if action_code == "taken":
            order = fabricator_mark_taken(db, order_id, user)
        elif action_code in {"completed", "done"}:
            order = fabricator_mark_completed(db, order_id, user)
        else:
            return JSONResponse(status_code=400, content={"success": False, "message": "Acción no válida."})

        status = order.status
        return {
            "success": True,
            "status": status,
            "status_label": TRACKING_STATUS_LABELS.get(status, status),
            "message": (
                "Orden marcada como tomada."
                if action_code == "taken"
                else "Orden marcada como realizada — pasa a envío."
            ),
        }
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})


@router.get("/fabrication-condensed/export/excel")
async def fabrication_condensed_export_excel(
    request: Request,
    month: str = "",
    year: str = "",
    client_id: str = "",
    production_status: str = "",
    custom_filter: str = "",
    search: str = "",
    group_by: str = "order",
    show_completed: str = "",
    db: Session = Depends(get_db),
):
    user = _require_access(request)
    if isinstance(user, RedirectResponse):
        return user

    prepare_production_module(db)
    filters = parse_fabrication_filters(
        month=month,
        year=year,
        client_id=client_id,
        production_status=production_status,
        custom_filter=custom_filter,
        search=search,
        group_by=group_by,
        show_completed=show_completed,
        apply_current_month_default=True,
    )
    groups = get_fabrication_order_groups(db, **filters)
    buffer = export_fabrication_excel(groups)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="condensado_fabricacion.xlsx"'},
    )


@router.get("/fabrication-condensed/export/pdf")
async def fabrication_condensed_export_pdf(
    request: Request,
    month: str = "",
    year: str = "",
    client_id: str = "",
    production_status: str = "",
    custom_filter: str = "",
    search: str = "",
    group_by: str = "order",
    show_completed: str = "",
    db: Session = Depends(get_db),
):
    user = _require_access(request)
    if isinstance(user, RedirectResponse):
        return user

    prepare_production_module(db)
    filters = parse_fabrication_filters(
        month=month,
        year=year,
        client_id=client_id,
        production_status=production_status,
        custom_filter=custom_filter,
        search=search,
        group_by=group_by,
        show_completed=show_completed,
        apply_current_month_default=True,
    )
    groups = get_fabrication_order_groups(db, **filters)
    config = db.query(CompanyConfig).first()
    issued_by = user.full_name or user.username if user else "Sistema ERP"

    month_part = ""
    if filters.get("year"):
        month_part = f"_{filters['year']:04d}"
        if filters.get("month"):
            month_part = f"_{filters['year']:04d}-{filters['month']:02d}"

    buffer = export_fabrication_pdf(
        groups,
        config=config,
        filters=filters,
        issued_by=issued_by,
        fabricator_name="",
    )

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="condensado_fabricacion{month_part}.pdf"'
            )
        },
    )
