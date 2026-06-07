from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.auth_handler import login_required, role_required

from app.models.inventory_movement import InventoryMovement

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

from app.utils.context import get_global_config
templates.env.globals['inject_global_config'] = get_global_config


@router.get(
    "/",
    response_class=HTMLResponse
)
async def inventory_page(
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin"]
    )

    if isinstance(user, RedirectResponse):
        return user

    movements = db.query(
        InventoryMovement
    ).order_by(
        InventoryMovement.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="inventory/list.html",
        context={
            "movements": movements
        }
    )