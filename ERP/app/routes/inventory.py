from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends

from fastapi.responses import HTMLResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.inventory_movement import InventoryMovement

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"]
)

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get(
    "/",
    response_class=HTMLResponse
)
async def inventory_page(
    request: Request,
    db: Session = Depends(get_db)
):

    movements = db.query(
        InventoryMovement
    ).order_by(
        InventoryMovement.id.desc()
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={
            "movements": movements
        }
    )