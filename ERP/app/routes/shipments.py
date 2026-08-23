from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.auth.auth_handler import role_required

from app.models.shipment import Shipment
from app.models.quotation import Quotation
from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.auth.security import verify_admin_password
from app.services.shipment_service import (
    DEFAULT_GUIDE_COLORS,
    GUIDE_QUOTATION_STATUSES,
    SHIPMENT_ROLES,
    _normalize_hex_color,
    apply_shipment_fields,
    build_label_context,
    count_pending_guide_quotations,
    get_guide_colors,
    get_latest_shipment,
    next_guide_number,
    pending_guide_quotations_query,
    quotation_can_have_guide,
    quotation_internal_status,
    serialize_pending_quotation,
    serialize_shipment_row,
)
from app.config.settings import settings
from app.utils.pagination import build_page_url, paginate_query


router = APIRouter(
    prefix="/shipments",
    tags=["shipments"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
from app.utils.image_storage import logo_image_url

templates.env.globals['inject_global_config'] = get_global_config
templates.env.globals['logo_image_url'] = logo_image_url
templates.env.globals["build_page_url"] = build_page_url


def _require_shipment_access(request: Request):
    return role_required(request, SHIPMENT_ROLES)


def _get_config(db: Session) -> CompanyConfig | None:
    return db.query(CompanyConfig).first()


def _parse_optional_int(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _render_label(request: Request, db: Session, label_data: dict, size: str = "a4"):
    label_data["print_size"] = "a5" if size.lower() == "a5" else "a4"
    if "colors" not in label_data:
        label_data["colors"] = get_guide_colors(_get_config(db))
    return templates.TemplateResponse(
        request=request,
        name="shipments/label.html",
        context={
            "label": label_data,
            "colors_saved": request.query_params.get("colors_saved", ""),
            "colors_error": request.query_params.get("colors_error", ""),
        },
    )


def _origin_city(db: Session) -> str:
    config = _get_config(db)
    return config.guide_sender_city if config and config.guide_sender_city else "Manta"


@router.post("/label-colors")
async def save_guide_label_colors(
    request: Request,
    accent: str = Form(""),
    border: str = Form(""),
    muted: str = Form(""),
    return_url: str = Form(""),
    db: Session = Depends(get_db),
):
    """Guarda colores de la etiqueta de guía (configuración empresa)."""
    from urllib.parse import urlparse

    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    config = _get_config(db)
    if not config:
        config = CompanyConfig()
        db.add(config)
        db.flush()

    config.guide_accent_color = _normalize_hex_color(accent, DEFAULT_GUIDE_COLORS["accent"])
    config.guide_border_color = _normalize_hex_color(border, DEFAULT_GUIDE_COLORS["border"])
    config.guide_muted_color = _normalize_hex_color(muted, DEFAULT_GUIDE_COLORS["muted"])
    db.commit()

    target = (return_url or "").strip()
    parsed = urlparse(target)
    if target.startswith("/shipments/") and not parsed.scheme and not parsed.netloc:
        sep = "&" if "?" in target else "?"
        return RedirectResponse(url=f"{target}{sep}colors_saved=1", status_code=302)
    return RedirectResponse(url="/shipments/?colors_saved=1", status_code=302)


# =========================================
# LISTADO DE GUÍAS
# =========================================

@router.get("/", response_class=HTMLResponse)
async def shipments_page(request: Request, db: Session = Depends(get_db)):
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    view = (request.query_params.get("view") or "pendientes").strip().lower()
    if view not in {"pendientes", "registradas"}:
        view = "pendientes"

    try:
        page = int(request.query_params.get("page") or 1)
    except ValueError:
        page = 1

    pending_total = count_pending_guide_quotations(db)
    registered_total = db.query(Shipment).count()
    with_quote = (
        db.query(Shipment).filter(Shipment.quotation_id.isnot(None)).count()
    )
    without_quote = registered_total - with_quote

    rows: list = []
    pagination = None
    if view == "pendientes":
        pagination = paginate_query(
            pending_guide_quotations_query(db), page, settings.per_page
        )
        rows = [serialize_pending_quotation(q) for q in pagination.items]
    else:
        shipments_q = (
            db.query(Shipment)
            .options(
                joinedload(Shipment.quotation).joinedload(Quotation.client),
                joinedload(Shipment.quotation).joinedload(Quotation.production_order),
                joinedload(Shipment.client),
            )
            .order_by(Shipment.id.desc())
        )
        pagination = paginate_query(shipments_q, page, settings.per_page)
        rows = [serialize_shipment_row(s) for s in pagination.items]

    open_label = request.query_params.get("open_label", "")
    open_size = request.query_params.get("size", "a4")
    filter_params = {"view": view}

    return templates.TemplateResponse(
        request=request,
        name="shipments/list.html",
        context={
            "rows": rows,
            "view": view,
            "user": user,
            "open_label": open_label,
            "open_size": open_size,
            "flash_deleted": request.query_params.get("deleted") == "1",
            "flash_error": request.query_params.get("error", ""),
            "flash_saved": request.query_params.get("saved") == "1",
            "stats_pending": pending_total,
            "stats_registered": registered_total,
            "stats_with_quote": with_quote,
            "stats_without_quote": without_quote,
            "page": pagination.page if pagination else 1,
            "pages": pagination.pages if pagination else 1,
            "total": pagination.total if pagination else 0,
            "filter_params": filter_params,
        },
    )


@router.get("/quotations", response_class=HTMLResponse)
async def shipments_quotations_picker(request: Request, db: Session = Depends(get_db)):
    """Cotizaciones aprobadas para generar o imprimir guía (paginado)."""
    from sqlalchemy import exists

    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    try:
        page = int(request.query_params.get("page") or 1)
    except ValueError:
        page = 1

    filter_mode = (request.query_params.get("filter") or "todas").strip().lower()
    if filter_mode not in {"todas", "pendientes", "con_guia"}:
        filter_mode = "todas"

    base_q = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.client),
            joinedload(Quotation.production_order),
        )
        .filter(Quotation.status.in_(list(GUIDE_QUOTATION_STATUSES)))
        .order_by(Quotation.id.desc())
    )
    has_shipment = exists().where(Shipment.quotation_id == Quotation.id)
    if filter_mode == "pendientes":
        base_q = base_q.filter(~has_shipment)
    elif filter_mode == "con_guia":
        base_q = base_q.filter(has_shipment)

    pagination = paginate_query(base_q, page, settings.per_page)
    rows = []
    for q in pagination.items:
        client = q.client
        shipment = get_latest_shipment(db, q.id)
        internal = quotation_internal_status(q)
        rows.append({
            "id": q.id,
            "client_name": client.name if client else "—",
            "status": q.status,
            "has_guide": shipment is not None,
            "guide_number": shipment.guide_number if shipment else None,
            "shipment_id": shipment.id if shipment else None,
            **internal,
        })

    open_label = request.query_params.get("open_label", "")
    open_size = request.query_params.get("size", "a4")
    return templates.TemplateResponse(
        request=request,
        name="shipments/quotations.html",
        context={
            "rows": rows,
            "user": user,
            "open_label": open_label,
            "open_size": open_size,
            "page": pagination.page,
            "pages": pagination.pages,
            "total": pagination.total,
            "filter_mode": filter_mode,
            "filter_params": {"filter": filter_mode},
        },
    )


@router.get("/quotation/{quotation_id}/label", response_class=HTMLResponse)
async def quotation_label(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Imprime guía desde cotización aprobada (usa guía existente o borrador)."""
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    size = request.query_params.get("size", "a4")

    quotation = (
        db.query(Quotation)
        .options(joinedload(Quotation.client), joinedload(Quotation.production_order))
        .filter(Quotation.id == quotation_id)
        .first()
    )
    if not quotation or not quotation_can_have_guide(quotation):
        return RedirectResponse(url="/shipments/quotations", status_code=302)

    shipment = get_latest_shipment(db, quotation_id)
    config = _get_config(db)
    label_data = build_label_context(
        shipment=shipment,
        quotation=quotation,
        client=quotation.client,
        config=config,
        size=size,
    )
    return _render_label(request, db, label_data, size)


# =========================================
# NUEVA / EDITAR GUÍA
# =========================================

@router.get("/new", response_class=HTMLResponse)
async def new_shipment_standalone(request: Request, db: Session = Depends(get_db)):
    """Guía sin cotización: seleccionar o registrar cliente."""
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    clients = db.query(Client).order_by(Client.name.asc()).all()
    client_id = _parse_optional_int(request.query_params.get("client_id"))
    client = db.query(Client).filter(Client.id == client_id).first() if client_id else None

    return templates.TemplateResponse(
        request=request,
        name="shipments/new.html",
        context={
            "quotation": None,
            "client": client,
            "clients": clients,
            "existing": None,
            "edit_mode": False,
            "standalone": True,
            "status_info": None,
            "user": user,
            "error": request.query_params.get("error", ""),
        },
    )


@router.get("/new/{quotation_id}", response_class=HTMLResponse)
async def new_shipment(quotation_id: int, request: Request, db: Session = Depends(get_db)):
    """Si ya hay guía para la cotización, redirige a editar (1:1 en todo el sistema)."""
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    quotation = (
        db.query(Quotation)
        .options(joinedload(Quotation.client), joinedload(Quotation.production_order))
        .filter(Quotation.id == quotation_id)
        .first()
    )

    if not quotation or not quotation_can_have_guide(quotation):
        return RedirectResponse(url="/shipments/quotations", status_code=302)

    existing = get_latest_shipment(db, quotation_id)
    if existing:
        return RedirectResponse(url=f"/shipments/{existing.id}/edit", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="shipments/new.html",
        context={
            "quotation": quotation,
            "client": quotation.client,
            "clients": None,
            "existing": None,
            "edit_mode": False,
            "standalone": False,
            "status_info": quotation_internal_status(quotation),
            "user": user,
            "error": "",
        },
    )


@router.get("/{shipment_id}/edit", response_class=HTMLResponse)
async def edit_shipment(shipment_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    shipment = (
        db.query(Shipment)
        .options(
            joinedload(Shipment.quotation).joinedload(Quotation.client),
            joinedload(Shipment.quotation).joinedload(Quotation.production_order),
            joinedload(Shipment.client),
        )
        .filter(Shipment.id == shipment_id)
        .first()
    )
    if not shipment:
        return RedirectResponse(url="/shipments/", status_code=302)

    quotation = shipment.quotation
    client = None
    if quotation and quotation.client:
        client = quotation.client
    elif shipment.client:
        client = shipment.client

    return templates.TemplateResponse(
        request=request,
        name="shipments/new.html",
        context={
            "quotation": quotation,
            "client": client,
            "clients": None,
            "existing": shipment,
            "edit_mode": True,
            "standalone": quotation is None,
            "status_info": quotation_internal_status(quotation) if quotation else None,
            "user": user,
            "error": "",
        },
    )


@router.post("/create")
async def create_shipment(
    request: Request,
    customer_name: str = Form(...),
    customer_id_number: str = Form(""),
    customer_phone: str = Form(...),
    destination_city: str = Form(...),
    destination_address: str = Form(...),
    carrier: str = Form(...),
    boxes: int = Form(...),
    notes: str = Form(""),
    quotation_id: str = Form(""),
    client_id: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    qid = _parse_optional_int(quotation_id)
    cid = _parse_optional_int(client_id)

    quotation = None
    client = None

    if qid:
        quotation = db.query(Quotation).filter(Quotation.id == qid).first()
        if not quotation or not quotation_can_have_guide(quotation):
            return RedirectResponse(url="/shipments/quotations", status_code=302)
        if quotation.client_id:
            cid = quotation.client_id
        # Upsert: una sola guía por cotización
        existing = get_latest_shipment(db, qid)
        if existing:
            apply_shipment_fields(
                existing,
                customer_name=customer_name,
                customer_id_number=customer_id_number,
                customer_phone=customer_phone,
                destination_city=destination_city,
                destination_address=destination_address,
                carrier=carrier,
                boxes=boxes,
                notes=notes,
            )
            if cid and not existing.client_id:
                existing.client_id = cid
            db.commit()
            return RedirectResponse(
                url=f"/shipments/?view=registradas&open_label={existing.id}&size=a4&saved=1",
                status_code=302,
            )
    else:
        if not cid:
            return RedirectResponse(
                url="/shipments/new?error=cliente",
                status_code=302,
            )
        client = db.query(Client).filter(Client.id == cid).first()
        if not client:
            return RedirectResponse(
                url="/shipments/new?error=cliente",
                status_code=302,
            )

    if cid and client is None:
        client = db.query(Client).filter(Client.id == cid).first()

    shipment = Shipment(
        quotation_id=qid,
        client_id=cid,
        guide_number=next_guide_number(db),
        origin_city=_origin_city(db),
        status="pendiente",
    )
    apply_shipment_fields(
        shipment,
        customer_name=customer_name,
        customer_id_number=customer_id_number,
        customer_phone=customer_phone,
        destination_city=destination_city,
        destination_address=destination_address,
        carrier=carrier,
        boxes=boxes,
        notes=notes,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    return RedirectResponse(
        url=f"/shipments/?view=registradas&open_label={shipment.id}&size=a4&saved=1",
        status_code=302,
    )


@router.post("/{shipment_id}/update")
async def update_shipment(
    shipment_id: int,
    request: Request,
    customer_name: str = Form(...),
    customer_id_number: str = Form(""),
    customer_phone: str = Form(...),
    destination_city: str = Form(...),
    destination_address: str = Form(...),
    carrier: str = Form(...),
    boxes: int = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        return RedirectResponse(url="/shipments/?view=registradas", status_code=302)

    apply_shipment_fields(
        shipment,
        customer_name=customer_name,
        customer_id_number=customer_id_number,
        customer_phone=customer_phone,
        destination_city=destination_city,
        destination_address=destination_address,
        carrier=carrier,
        boxes=boxes,
        notes=notes,
    )
    db.commit()

    return RedirectResponse(
        url=f"/shipments/?view=registradas&open_label={shipment_id}&size=a4&saved=1",
        status_code=302,
    )


@router.post("/{shipment_id}/delete")
async def delete_shipment(
    shipment_id: int,
    request: Request,
    admin_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    if not verify_admin_password(admin_password):
        return RedirectResponse(
            url="/shipments/?error=clave_admin_incorrecta",
            status_code=302,
        )

    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        return RedirectResponse(url="/shipments/", status_code=302)

    db.delete(shipment)
    db.commit()

    return RedirectResponse(
        url="/shipments/?deleted=1",
        status_code=302,
    )


# =========================================
# IMPRIMIR GUÍA (registro existente)
# =========================================

@router.get("/{shipment_id}/label", response_class=HTMLResponse)
async def shipment_label(
    shipment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    size = request.query_params.get("size", "a4")

    shipment = (
        db.query(Shipment)
        .options(
            joinedload(Shipment.quotation).joinedload(Quotation.client),
            joinedload(Shipment.quotation).joinedload(Quotation.production_order),
            joinedload(Shipment.client),
        )
        .filter(Shipment.id == shipment_id)
        .first()
    )
    if not shipment:
        return RedirectResponse(url="/shipments/", status_code=302)

    config = _get_config(db)
    client = None
    if shipment.quotation and shipment.quotation.client:
        client = shipment.quotation.client
    elif shipment.client:
        client = shipment.client

    label_data = build_label_context(
        shipment=shipment,
        quotation=shipment.quotation,
        client=client,
        config=config,
        size=size,
    )
    return _render_label(request, db, label_data, size)


@router.get("/{shipment_id}/print")
async def print_shipment(
    request: Request,
    shipment_id: int,
    db: Session = Depends(get_db),
):
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    size = request.query_params.get("size", "a4")
    return RedirectResponse(
        url=f"/shipments/{shipment_id}/label?size={size}",
        status_code=302,
    )
