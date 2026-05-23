from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.auth_handler import login_required

from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation
from app.models.production_order import ProductionOrder
from app.models.company_config import CompanyConfig

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config


@router.get(
    "/",
    response_class=HTMLResponse
)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db)
):

    user = login_required(request)

    if isinstance(user, RedirectResponse):
        return user

    total_clients = db.query(Client).count()

    total_products = db.query(Product).count()

    total_quotations = db.query(Quotation).count()

    production_pending = db.query(
    ProductionOrder
).filter(
    ProductionOrder.status.in_([
        "pendiente",
        "diseño",
        "produccion",
        "empacado"
    ])
).count()
    recent_quotations = db.query(
        Quotation
    ).order_by(
        Quotation.id.desc()
    ).limit(5).all()

    config = db.query(CompanyConfig).first()
    company_name = config.company_name if config else "SISTEMA ERP"

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "total_clients": total_clients,
            "total_products": total_products,
            "total_quotations": total_quotations,
            "production_pending": production_pending,
            "recent_quotations": recent_quotations,
            "company_name": company_name
        }
    )