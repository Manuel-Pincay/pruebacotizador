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
    SHIPMENT_ROLES,
    build_label_context,
    get_latest_shipment,
    list_quotations_for_guides,
    quotation_can_have_guide,
    quotation_internal_status,
)


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


def _require_shipment_access(request: Request):
    return role_required(request, SHIPMENT_ROLES)


def _get_config(db: Session) -> CompanyConfig | None:
    return db.query(CompanyConfig).first()


def _render_label(request: Request, db: Session, label_data: dict, size: str = "a4"):
    label_data["print_size"] = "a5" if size.lower() == "a5" else "a4"
    return templates.TemplateResponse(
        request=request,
        name="shipments/label.html",
        context={"label": label_data},
    )


# =========================================
# LISTADO DE GUÍAS
# =========================================

@router.get("/", response_class=HTMLResponse)
async def shipments_page(request: Request, db: Session = Depends(get_db)):
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    shipments = (
        db.query(Shipment)
        .options(
            joinedload(Shipment.quotation).joinedload(Quotation.client),
            joinedload(Shipment.quotation).joinedload(Quotation.production_order),
        )
        .order_by(Shipment.id.desc())
        .all()
    )

    open_label = request.query_params.get("open_label", "")
    open_size = request.query_params.get("size", "a4")

    return templates.TemplateResponse(
        request=request,
        name="shipments/list.html",
        context={
            "shipments": shipments,
            "user": user,
            "open_label": open_label,
            "open_size": open_size,
            "flash_deleted": request.query_params.get("deleted") == "1",
            "flash_error": request.query_params.get("error", ""),
        },
    )


@router.get("/quotations", response_class=HTMLResponse)
async def shipments_quotations_picker(request: Request, db: Session = Depends(get_db)):
    """Cotizaciones aprobadas para generar o imprimir guía."""
    user = _require_shipment_access(request)
    if isinstance(user, RedirectResponse):
        return user

    rows = list_quotations_for_guides(db)
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

@router.get("/new/{quotation_id}", response_class=HTMLResponse)
async def new_shipment(quotation_id: int, request: Request, db: Session = Depends(get_db)):
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

    client = quotation.client
    existing = get_latest_shipment(db, quotation_id)

    return templates.TemplateResponse(
        request=request,
        name="shipments/new.html",
        context={
            "quotation": quotation,
            "client": client,
            "existing": existing,
            "edit_mode": False,
            "status_info": quotation_internal_status(quotation),
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
        )
        .filter(Shipment.id == shipment_id)
        .first()
    )
    if not shipment or not shipment.quotation:
        return RedirectResponse(url="/shipments/", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="shipments/new.html",
        context={
            "quotation": shipment.quotation,
            "client": shipment.quotation.client,
            "existing": shipment,
            "edit_mode": True,
            "status_info": quotation_internal_status(shipment.quotation),
        },
    )


@router.post("/create")
async def create_shipment(
    request: Request,
    quotation_id: int = Form(...),
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

    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation or not quotation_can_have_guide(quotation):
        return RedirectResponse(url="/shipments/quotations", status_code=302)

    shipment_count = db.query(Shipment).count()
    guide_number = f"G-{shipment_count + 1:05d}"

    config = _get_config(db)
    origin_city = config.guide_sender_city if config and config.guide_sender_city else "Manta"

    shipment = Shipment(
        quotation_id=quotation_id,
        guide_number=guide_number,
        customer_name=customer_name.strip(),
        customer_id_number=customer_id_number.strip() or None,
        customer_phone=customer_phone.strip(),
        origin_city=origin_city,
        destination_city=destination_city.strip(),
        destination_address=destination_address.strip(),
        carrier=carrier.strip(),
        boxes=boxes,
        notes=notes.strip() or None,
        status="pendiente",
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    return RedirectResponse(
        url=f"/shipments/quotations?open_label={shipment.id}&size=a4",
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
        return RedirectResponse(url="/shipments/", status_code=302)

    shipment.customer_name = customer_name.strip()
    shipment.customer_id_number = customer_id_number.strip() or None
    shipment.customer_phone = customer_phone.strip()
    shipment.destination_city = destination_city.strip()
    shipment.destination_address = destination_address.strip()
    shipment.carrier = carrier.strip()
    shipment.boxes = boxes
    shipment.notes = notes.strip() or None
    db.commit()

    return RedirectResponse(
        url=f"/shipments/quotations?open_label={shipment_id}&size=a4",
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
            url=f"/shipments/?error=clave_admin_incorrecta",
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
        )
        .filter(Shipment.id == shipment_id)
        .first()
    )
    if not shipment or not shipment.quotation:
        return RedirectResponse(url="/shipments/", status_code=302)

    config = _get_config(db)
    label_data = build_label_context(
        shipment=shipment,
        quotation=shipment.quotation,
        client=shipment.quotation.client,
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
