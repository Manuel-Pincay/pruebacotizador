from fastapi import APIRouter, Depends, Form, Request

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session, joinedload



from app.auth.auth_handler import role_required

from app.auth.design_permissions import (
    can_view_design_item,
    designer_item_scope_user_id,
    is_design_admin,
)

from app.auth.permissions import ROLE_ADMIN, ROLE_DISENADOR

from app.database import get_db

from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem

from app.models.user import User

from app.services.design_service import (

    DESIGN_STATUS_COLORS,

    DESIGN_STATUS_LABELS,

    DESIGN_STATUSES,

    add_design_observation,

    assign_designer,

    compute_design_kpis,

    get_design_detail,

    list_design_items,

    list_designers,

    update_design_status,

)

from app.utils.context import get_global_config

from app.utils.image_storage import design_image_url



router = APIRouter(prefix="/design", tags=["design"])



templates = Jinja2Templates(directory="app/templates")

templates.env.globals["inject_global_config"] = get_global_config

templates.env.globals["design_image_url"] = design_image_url

templates.env.globals["design_status_colors"] = DESIGN_STATUS_COLORS



DESIGN_ROLES = [ROLE_ADMIN, ROLE_DISENADOR]





def _require_design_access(request: Request):

    user = role_required(request, DESIGN_ROLES)

    if isinstance(user, RedirectResponse):

        return user

    return user





def _load_item_for_access(db: Session, item_id: int) -> QuotationItem | None:

    return (
        db.query(QuotationItem)
        .options(
            joinedload(QuotationItem.design_tracking),
            joinedload(QuotationItem.quotation).joinedload(Quotation.production_order),
        )
        .filter(QuotationItem.id == item_id)
        .first()
    )





@router.get("/dashboard", response_class=HTMLResponse)

async def design_dashboard(request: Request, db: Session = Depends(get_db)):

    user = _require_design_access(request)

    if isinstance(user, RedirectResponse):

        return user



    designer_scope = designer_item_scope_user_id(user)

    kpis = compute_design_kpis(db, designer_scope_user_id=designer_scope)

    recent = list_design_items(

        db,

        design_filter="pending",

        designer_scope_user_id=designer_scope,

        limit=8,

    )



    return templates.TemplateResponse(

        request=request,

        name="design/dashboard.html",

        context={

            "user": user,

            "kpis": kpis,

            "recent_items": recent,

            "design_statuses": DESIGN_STATUSES,

        },

    )





@router.get("/pending", response_class=HTMLResponse)

async def design_pending(

    request: Request,

    filter: str = "pending",

    db: Session = Depends(get_db),

):

    user = _require_design_access(request)

    if isinstance(user, RedirectResponse):

        return user



    designer_scope = designer_item_scope_user_id(user)

    assigned_id = user.id if user.role == ROLE_DISENADOR and filter == "mine" else None

    if filter == "mine":

        design_filter = "mine"

    elif filter in {"diseno", "produccion", "envio", "entregado"}:

        design_filter = filter

    else:

        design_filter = "pending"



    rows = list_design_items(

        db,

        design_filter=design_filter,

        assigned_user_id=assigned_id,

        designer_scope_user_id=designer_scope if filter != "mine" else None,

    )



    return templates.TemplateResponse(

        request=request,

        name="design/pending.html",

        context={

            "user": user,

            "rows": rows,

            "active_filter": filter,

            "design_statuses": DESIGN_STATUSES,

            "designers": list_designers(db) if is_design_admin(user) else [],

        },

    )





@router.get("/profile", response_class=HTMLResponse)

async def design_profile(request: Request, db: Session = Depends(get_db)):

    user = _require_design_access(request)

    if isinstance(user, RedirectResponse):

        return user



    return templates.TemplateResponse(

        request=request,

        name="design/profile.html",

        context={"user": user},

    )





@router.get("/items/{item_id}", response_class=HTMLResponse)

async def design_detail_page(

    item_id: int,

    request: Request,

    db: Session = Depends(get_db),

):

    user = _require_design_access(request)

    if isinstance(user, RedirectResponse):

        return user



    item = _load_item_for_access(db, item_id)

    if not item or not can_view_design_item(user, item):

        return RedirectResponse(url="/design/pending", status_code=302)



    detail = get_design_detail(db, item_id)

    if not detail:

        return RedirectResponse(url="/design/pending", status_code=302)



    return templates.TemplateResponse(

        request=request,

        name="design/detail.html",

        context={

            "user": user,

            "detail": detail,

            "designers": list_designers(db) if is_design_admin(user) else [],

            "design_statuses": DESIGN_STATUSES,

        },

    )





@router.post("/items/{item_id}/status")

async def design_update_status(

    item_id: int,

    request: Request,

    action: str = Form(...),

    note: str = Form(""),

    db: Session = Depends(get_db),

):

    user = _require_design_access(request)

    if isinstance(user, RedirectResponse):

        return user



    item = _load_item_for_access(db, item_id)

    if not item or not can_view_design_item(user, item):

        return JSONResponse(status_code=403, content={"success": False, "message": "Sin permiso."})



    action_map = {

        "start": "start",

        "diseno": "diseno",

    }

    status = action_map.get(action)

    if not status:

        return JSONResponse(

            status_code=400,

            content={

                "success": False,

                "message": "Para completar el diseño use Datos de fabricación → Enviar a producción.",

            },

        )



    try:

        result = update_design_status(

            db,

            item_id,

            status=status,

            user=user,

            note=note,

        )

        return {

            "success": True,

            "status": result["status"],

            "status_label": result["status_label"],

            "production_order_id": result.get("production_order_id"),

        }

    except ValueError as exc:

        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})





@router.post("/items/{item_id}/observations")

async def design_add_observation(

    item_id: int,

    request: Request,

    note: str = Form(...),

    db: Session = Depends(get_db),

):

    user = _require_design_access(request)

    if isinstance(user, RedirectResponse):

        return user



    item = _load_item_for_access(db, item_id)

    if not item or not can_view_design_item(user, item):

        return JSONResponse(status_code=403, content={"success": False, "message": "Sin permiso."})



    try:

        observation = add_design_observation(db, item_id, user=user, note=note)

        return {

            "success": True,

            "observation": {

                "id": observation.id,

                "user_name": observation.user_name,

                "note": observation.note,

                "created_at": observation.created_at.isoformat() if observation.created_at else None,

            },

        }

    except ValueError as exc:

        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})





@router.post("/items/{item_id}/assign")

async def design_assign(

    item_id: int,

    request: Request,

    designer_user_id: str = Form(""),

    note: str = Form(""),

    db: Session = Depends(get_db),

):

    user = role_required(request, [ROLE_ADMIN])

    if isinstance(user, RedirectResponse):

        return user



    parsed_designer_id = int(designer_user_id) if designer_user_id.strip().isdigit() else None



    try:

        order = assign_designer(

            db,

            item_id,

            designer_user_id=parsed_designer_id,

            note=note,

            actor=user,

        )

        assigned = "—"

        if order and order.assignee:

            assigned = order.assignee.full_name or order.assignee.username or "—"

        elif order and order.designer:

            assigned = order.designer

        return {"success": True, "assigned_to": assigned}

    except ValueError as exc:

        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})






from app.routes import design_production
router.include_router(design_production.router)
