from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.auth_handler import login_required, role_required

from app.models.shipment import Shipment
from app.models.quotation import Quotation
from app.models.client import Client
from app.models.company_config import CompanyConfig


router = APIRouter(
    prefix="/shipments",
    tags=["shipments"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config


# =========================================
# LISTADO DE GUÍAS
# =========================================

@router.get(
    "/",
    response_class=HTMLResponse
)
async def shipments_page(
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "despacho"]
    )

    if isinstance(user, RedirectResponse):
        return user

    shipments = db.query(
        Shipment
    ).order_by(
        Shipment.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="shipments.html",
        context={
            "shipments": shipments
        }
    )


# =========================================
# NUEVA GUÍA
# =========================================

@router.get(
    "/new/{quotation_id}",
    response_class=HTMLResponse
)
async def new_shipment(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "despacho"]
    )

    if isinstance(user, RedirectResponse):
        return user

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations/",
            status_code=302
        )

    client = db.query(
        Client
    ).filter(
        Client.id == quotation.client_id
    ).first()

    return templates.TemplateResponse(
        request=request,
        name="shipment_new.html",
        context={
            "quotation": quotation,
            "client": client
        }
    )


# =========================================
# CREAR GUÍA
# =========================================

@router.post("/create")
async def create_shipment(

    quotation_id: int = Form(...),

    customer_name: str = Form(...),

    customer_phone: str = Form(...),

    destination_city: str = Form(...),

    destination_address: str = Form(...),

    carrier: str = Form(...),

    boxes: int = Form(...),

    notes: str = Form(""),

    db: Session = Depends(get_db)

):

    shipment_count = db.query(
        Shipment
    ).count()

    guide_number = f"G-{shipment_count + 1:05}"


    shipment = Shipment(

        quotation_id=quotation_id,

        guide_number=guide_number,

        customer_name=customer_name,

        customer_phone=customer_phone,

        origin_city="Manta",

        destination_city=destination_city,

        destination_address=destination_address,

        carrier=carrier,

        boxes=boxes,

        notes=notes,

        #barcode_image=barcode_image,

        status="pendiente"

    )

    db.add(shipment)

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if quotation:

        quotation.status = "enviado"

    db.commit()

    db.refresh(shipment)

    return RedirectResponse(
        url=f"/shipments/{shipment.id}/label",
        status_code=302
    )


# =========================================
# ETIQUETA
# =========================================

@router.get(
    "/{shipment_id}/label",
    response_class=HTMLResponse
)
async def shipment_label(
    shipment_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin", "despacho"]
    )

    if isinstance(user, RedirectResponse):
        return user

    shipment = db.query(
        Shipment
    ).filter(
        Shipment.id == shipment_id
    ).first()

    if not shipment:

        return RedirectResponse(
            url="/shipments/",
            status_code=302
        )

    config = db.query(CompanyConfig).first()
    company_name = config.company_name if config else "SISTEMA ERP"

    return templates.TemplateResponse(
        request=request,
        name="shipment_label.html",
        context={
            "shipment": shipment,
            "company_name": company_name
        }
    )


# =========================================
# IMPRIMIR
# =========================================

@router.get("/{shipment_id}/print")
async def print_shipment(
    shipment_id: int
):

    return RedirectResponse(
        url=f"/shipments/{shipment_id}/label",
        status_code=302
    )