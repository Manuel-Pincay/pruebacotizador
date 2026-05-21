import json
from urllib import request

from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from fastapi.responses import FileResponse
from datetime import date
from datetime import timedelta

from app.models import quotation
from app.utils.pdf import generate_quotation_pdf

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.production_order import ProductionOrder
from app.models.inventory_movement import InventoryMovement

router = APIRouter(
    prefix="/quotations",
    tags=["quotations"]
)

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get(
    "/new",
    response_class=HTMLResponse
)
async def new_quotation(
    request: Request,
    db: Session = Depends(get_db)
):

    clients = db.query(Client).all()

    products = db.query(Product).all()

    return templates.TemplateResponse(
    request=request,
    name="quotation_new.html",
    context={
        "clients": clients,
        "products": products
    }
)

@router.get(
    "/",
    response_class=HTMLResponse
)
async def quotations_page(
    request: Request,
    db: Session = Depends(get_db)
):

    quotations = db.query(
        Quotation
    ).order_by(
        Quotation.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="quotations.html",
        context={
            "quotations": quotations
        }
    )

@router.get(
    "/{quotation_id}",
    response_class=HTMLResponse
)
async def quotation_detail(
    quotation_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    return templates.TemplateResponse(
        request=request,
        name="quotation_detail.html",
        context={
            "quotation": quotation
        }
    )

@router.get("/{quotation_id}/approve")
async def approve_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO PENDIENTES
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # APROBAR
    quotation.status = "aprobada"

    db.commit()

    return RedirectResponse(
        url=f"/quotations/{quotation_id}",
        status_code=302
    )

@router.get("/{quotation_id}/cancel")
async def cancel_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO SI ESTÁ PENDIENTE
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    quotation.status = "cancelada"

    db.commit()

    return RedirectResponse(
        url="/quotations",
        status_code=302
    )

@router.get("/{quotation_id}/delete")
async def delete_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO PENDIENTES
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # BORRAR ITEMS
    db.query(
        QuotationItem
    ).filter(
        QuotationItem.quotation_id == quotation.id
    ).delete()

    # BORRAR COTIZACIÓN
    db.delete(quotation)

    db.commit()

    return RedirectResponse(
        url="/quotations",
        status_code=302
    )

@router.get("/{quotation_id}/edit",
    response_class=HTMLResponse
)
async def edit_quotation_page(

    quotation_id: int,

    request: Request,

    db: Session = Depends(get_db)

):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO PENDIENTES
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    clients = db.query(Client).all()

    products = db.query(Product).all()

    items = db.query(
        QuotationItem
    ).filter(
        QuotationItem.quotation_id == quotation.id
    ).all()

    # ITEMS PARA JS
    items_json = []

    for item in items:

        items_json.append({

            "type": "inventory",

            "product_id": None,

            "quantity": item.quantity,

            "detail": item.detail,

            "price": item.unit_price,

            "total": item.total

        })

    return templates.TemplateResponse(

        request=request,

        name="quotation_new.html",

        context={

            "clients": clients,

            "products": products,

            "quotation": quotation,

            "items_json": json.dumps(items_json),

            "edit_mode": True

        }

    )

@router.post("/{quotation_id}/edit")
async def update_quotation(

    quotation_id: int,

    client_id: int = Form(...),

    subtotal: float = Form(...),

    discount: float = Form(...),

    iva: float = Form(...),

    total: float = Form(...),

    items: str = Form(...),

    db: Session = Depends(get_db)

):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    if not quotation:

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # SOLO PENDIENTES
    if quotation.status != "pendiente":

        return RedirectResponse(
            url="/quotations",
            status_code=302
        )

    # UPDATE HEADER
    quotation.client_id = client_id

    quotation.subtotal = subtotal

    quotation.discount = discount

    quotation.iva = iva

    quotation.total = total

    # DELETE OLD ITEMS
    db.query(
        QuotationItem
    ).filter(
        QuotationItem.quotation_id == quotation.id
    ).delete()

    items_data = json.loads(items)

    # INSERT NEW ITEMS
    for item in items_data:

        quotation_item = QuotationItem(

            quotation_id=quotation.id,

            quantity=item.get(
                "quantity",
                1
            ),

            detail=item.get(
                "detail",
                ""
            ),

            unit_price=item.get(
                "price",
                0.0
            ),

            total=item.get(
                "total",
                0.0
            )

        )

        db.add(quotation_item)

    db.commit()

    return RedirectResponse(

        url=f"/quotations/{quotation.id}",

        status_code=302

    )



@router.get("/{quotation_id}/production")
async def production_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

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

    quotation.status = "produccion"

    production_order = ProductionOrder(

        quotation_id=quotation.id,

        status="pendiente",

        priority="media",

        delivery_date=date.today() + timedelta(days=3)

    )

    db.add(production_order)

    db.commit()

    return RedirectResponse(
        url="/production/",
        status_code=302
    )

@router.get("/{quotation_id}/shipping")
async def shipping_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    quotation.status = "enviada"

    db.commit()

    if quotation.status != "produccion":

        return RedirectResponse(
        url=f"/quotations/{quotation_id}",
        status_code=302
    )


@router.get("/{quotation_id}/delivered")
async def delivered_quotation(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    quotation.status = "entregada"

    db.commit()

    return RedirectResponse(
        url=f"/quotations/{quotation_id}",
        status_code=302
    )

@router.get("/{quotation_id}/pdf")
async def quotation_pdf(
    quotation_id: int,
    db: Session = Depends(get_db)
):

    quotation = db.query(
        Quotation
    ).filter(
        Quotation.id == quotation_id
    ).first()

    items = db.query(
        QuotationItem
    ).filter(
        QuotationItem.quotation_id == quotation_id
    ).all()

    client = db.query(
        Client
    ).filter(
        Client.id == quotation.client_id
    ).first()

    filename = f"quotation_{quotation_id}.pdf"

    generate_quotation_pdf(
    quotation,
    items,
    client,
    filename
)

    return FileResponse(
        path=filename,
        media_type="application/pdf",
        filename=filename
    )

@router.post("/create")
async def create_quotation(

    client_id: int = Form(...),

    subtotal: float = Form(...),

    discount: float = Form(...),

    iva: float = Form(...),

    total: float = Form(...),

    items: str = Form(...),

    db: Session = Depends(get_db)

):

    quotation = Quotation(

        client_id=client_id,

        subtotal=subtotal,

        discount=discount,

        iva=iva,

        total=total,

        status="pendiente"

    )

    db.add(quotation)

    db.commit()

    db.refresh(quotation)

    items_data = json.loads(items)

    for item in items_data:

        quotation_item = QuotationItem(

            quotation_id=quotation.id,

            quantity=item.get(
                "quantity",
                1
            ),

            detail=item.get(
                "detail",
                ""
            ),

            measure=item.get(
                "measure",
                ""
            ),

            shape=item.get(
                "shape",
                ""
            ),

            color=item.get(
                "color",
                ""
            ),

            logo=item.get(
                "logo",
                ""
            ),

            unit_price=item.get(
    "price",
    0.0
),

            total=item.get(
                "total",
                0.0
            )

        )

        db.add(quotation_item)

    db.commit()

    return RedirectResponse(

        url=f"/quotations/{quotation.id}",

        status_code=302

    )