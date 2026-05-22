from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from datetime import date
from collections import defaultdict

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.auth_handler import login_required, role_required

from app.models.production_order import ProductionOrder
from app.models.quotation import Quotation

router = APIRouter(
    prefix="/production",
    tags=["production"]
)

templates = Jinja2Templates(
    directory="app/templates"
)


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

    orders = db.query(
    ProductionOrder
    ).filter(
        ProductionOrder.status != "enviado",
        ProductionOrder.status != "entregado"
    ).order_by(
        ProductionOrder.delivery_date.asc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="production.html",
        context={
            "orders": orders
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

    pending = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "pendiente"
    ).all()

    designing = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "diseño"
    ).all()

    producing = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "produccion"
    ).all()

    packed = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "empacado"
    ).all()

    shipped = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status == "enviado"
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="production_kanban.html",
        context={
            "pending": pending,
            "designing": designing,
            "producing": producing,
            "packed": packed,
            "shipped": shipped
        }
    )

# =========================================
# CALENDARIO PRODUCCIÓN
# =========================================

@router.get(
    "/calendar",
    response_class=HTMLResponse
)
async def production_calendar(
    request: Request,
    db: Session = Depends(get_db)
):

    quotations = db.query(
        Quotation
    ).filter(
        Quotation.delivery_date != None
    ).order_by(
        Quotation.delivery_date.asc()
    ).all()

    grouped_orders = defaultdict(list)

    for quotation in quotations:

        grouped_orders[
            quotation.delivery_date
        ].append(quotation)

    return templates.TemplateResponse(
        request=request,
        name="production_calendar.html",
        context={
            "grouped_orders": dict(grouped_orders),
            "today": date.today()
        }
    )

# =========================================
# CAMBIO DE ESTADO
# =========================================

@router.get("/move/{order_id}/{status}")
async def move_order(
    order_id: int,
    status: str,
    db: Session = Depends(get_db)
):

    order = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.id == order_id
    ).first()

    order.status = status

    db.commit()

    return RedirectResponse(
        url="/production/kanban",
        status_code=302
    )
# =========================================
# ACTUALIZAR ORDEN
# =========================================

@router.post(
    "/{order_id}/update/"
)
async def update_production(
    order_id: int,
    designer: str = Form(""),
    
    fabricator: str = Form(""),
    priority: str = Form("media"),
    observations: str = Form(""),
    status: str = Form("pendiente"),
    db: Session = Depends(get_db)
):

    order = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.id == order_id
    ).first()

    order.designer = designer

    order.fabricator = fabricator

    order.priority = priority

    order.observations = observations

    order.status = status

    db.commit()

    return RedirectResponse(
        url=f"/production/{order_id}",
        status_code=302
    )


# =========================================
# DETALLE ORDEN
# =========================================

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

    order = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.id == order_id
    ).first()

    return templates.TemplateResponse(
        request=request,
        name="production_detail.html",
        context={
            "order": order
        }
    )
