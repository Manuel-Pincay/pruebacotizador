from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends

from fastapi.responses import HTMLResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation
from app.models.production_order import ProductionOrder

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get(
    "/",
    response_class=HTMLResponse
)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db)
):

    total_clients = db.query(Client).count()

    total_products = db.query(Product).count()

    total_quotations = db.query(Quotation).count()

    production_pending = db.query(
        ProductionOrder
    ).filter(
        ProductionOrder.status != "terminado"
    ).count()

    recent_quotations = db.query(
        Quotation
    ).order_by(
        Quotation.id.desc()
    ).limit(5).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "total_clients": total_clients,
            "total_products": total_products,
            "total_quotations": total_quotations,
            "production_pending": production_pending,
            "recent_quotations": recent_quotations
        }
    )