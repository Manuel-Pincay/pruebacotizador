from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session, joinedload



from app.auth.auth_handler import role_required

from app.auth.design_permissions import (
    can_attach_design_images,
    can_edit_design_order,
    can_edit_fabrication_data,
    can_self_assign_design_item,
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

    claim_design_item,

    compute_design_kpis,

    get_design_detail,

    list_design_items,
    list_design_order_groups,
    list_shipping_queue,

    list_designers,

    update_design_status,

)

from app.services.design_catalog_service import list_design_sizes, list_usb_references
from app.services.production_order_service import (
    DESIGN_MATERIALS,
    build_order_dict,
    quotation_needs_fabrication,
)

from app.services.quotation_design_service import (
    DesignLimitError,
    add_design_image,
    delete_design_image,
    sync_legacy_design_file,
)
from app.utils.context import get_global_config
from app.utils.image_storage import (
    UploadValidationError,
    design_image_url,
    read_upload_bytes,
    validate_upload_filename,
)



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
            joinedload(QuotationItem.quotation).joinedload(Quotation.items).joinedload(QuotationItem.product),
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

    # Cola compartida: todos ven pendientes / en diseño
    queue_rows = list_design_order_groups(
        db,
        design_filter="pending",
        designer_scope_user_id=None,
        limit=12,
        sort_by="delivery",
    )
    available_items = [r for r in queue_rows if not r.get("assigned_to_user_id")][:8]
    recent = [r for r in queue_rows if r.get("production_status") in {"pendiente", "diseno"}][:8]

    return templates.TemplateResponse(
        request=request,
        name="design/dashboard.html",
        context={
            "user": user,
            "kpis": kpis,
            "available_items": available_items,
            "recent_items": recent,
            "shared_queue": True,
            "design_statuses": DESIGN_STATUSES,
            "claim_success": request.query_params.get("claimed", ""),
            "claim_error": request.query_params.get("claim_error", ""),
        },
    )





@router.get("/pending", response_class=HTMLResponse)
async def design_pending(
    request: Request,
    filter: str = "pending",
    sort: str = "delivery",
    db: Session = Depends(get_db),
):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    designer_scope = None  # cola compartida: todos ven todo
    assigned_id = user.id if user.role == ROLE_DISENADOR and filter == "mine" else None

    if filter == "mine":
        design_filter = "mine"
    elif filter in {"available", "disponibles", "unassigned"}:
        design_filter = "available"
    elif filter in {"diseno", "produccion", "envio", "entregado"}:
        design_filter = filter
    else:
        design_filter = "pending"

    allowed_sorts = {
        "delivery",
        "delivery_desc",
        "quotation",
        "quotation_desc",
        "client",
        "client_desc",
        "status",
        "status_desc",
        "designer",
        "designer_desc",
    }
    sort_by = sort if sort in allowed_sorts else "delivery"

    rows = list_design_order_groups(
        db,
        design_filter=design_filter,
        assigned_user_id=assigned_id,
        designer_scope_user_id=designer_scope,
        sort_by=sort_by,
    )
    for row in rows:
        # Marcar responsable es opcional; cualquier diseñador puede trabajar la orden
        row["can_claim"] = bool(
            user.role == ROLE_DISENADOR
            and row.get("production_status") in {"pendiente", "diseno"}
            and row.get("assigned_to_user_id") != user.id
        )
        row["can_work"] = bool(
            row.get("production_status") in {"pendiente", "diseno"}
            or is_design_admin(user)
        )

    active = "available" if design_filter == "available" else filter
    return templates.TemplateResponse(
        request=request,
        name="design/pending.html",
        context={
            "user": user,
            "rows": rows,
            "active_filter": active,
            "active_sort": sort_by,
            "design_statuses": DESIGN_STATUSES,
            "designers": list_designers(db) if is_design_admin(user) else [],
            "claim_error": request.query_params.get("claim_error", ""),
            "claim_success": request.query_params.get("claimed", ""),
        },
    )





@router.get("/shipping-today", response_class=HTMLResponse)
async def design_shipping_today(request: Request, db: Session = Depends(get_db)):
    """Cola de envíos para imprimir pedidos del día."""
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    rows = list_shipping_queue(db)
    today_rows = [row for row in rows if row.get("is_today")]
    other_rows = [row for row in rows if not row.get("is_today")]

    return templates.TemplateResponse(
        request=request,
        name="design/shipping_today.html",
        context={
            "user": user,
            "today_rows": today_rows,
            "other_rows": other_rows,
            "total_envio": len(rows),
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

    po = item.quotation.production_order if item.quotation else None
    client = item.quotation.client if item.quotation else None
    fabrication_order = (
        build_order_dict(po, client_name=client.name if client else "—") if po else None
    )
    needs_fabrication = any(
        not bool(p.get("fulfill_from_inventory"))
        for p in (detail.get("products") or [])
    ) if (detail.get("products") or []) else True
    can_edit_fabrication = bool(
        po
        and needs_fabrication
        and can_edit_fabrication_data(user, po)
    )

    return templates.TemplateResponse(

        request=request,

        name="design/detail.html",

        context={

            "user": user,

            "detail": detail,

            "designers": list_designers(db) if is_design_admin(user) else [],

            "design_statuses": DESIGN_STATUSES,

            "can_claim": bool(
                user.role == ROLE_DISENADOR
                and detail.get("can_claim")
            ),
            "can_attach_images": can_attach_design_images(user, item),
            "can_edit_products": can_attach_design_images(user, item)
            and (
                not item.quotation
                or not item.quotation.production_order
                or can_edit_design_order(user, item.quotation.production_order)
            ),
            "products_saved": request.query_params.get("products_saved", ""),
            "claimed": request.query_params.get("claimed", ""),
            "claim_error": request.query_params.get("claim_error", ""),
            "upload_ok": request.query_params.get("uploaded", ""),
            "upload_error": request.query_params.get("upload_error", ""),
            "needs_fabrication": needs_fabrication,
            "can_edit_fabrication": can_edit_fabrication,
            "fabrication_order": fabrication_order,
            "materials": DESIGN_MATERIALS,
            "sizes": list_design_sizes(db),
            "usb_references": list_usb_references(db),
        },
    )


@router.post("/items/{item_id}/products")
async def design_save_products_progress(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Marca productos listos e inventario/producción de toda la orden."""
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    item = _load_item_for_access(db, item_id)
    if not item or not can_view_design_item(user, item):
        return RedirectResponse(url="/design/pending", status_code=302)
    if not can_attach_design_images(user, item):
        return RedirectResponse(url=f"/design/items/{item_id}", status_code=302)

    po = item.quotation.production_order if item.quotation else None
    if po and not can_edit_design_order(user, po):
        return RedirectResponse(url=f"/design/items/{item_id}", status_code=302)

    from app.services.production_order_service import apply_quotation_item_fulfillment

    form = await request.form()
    apply_quotation_item_fulfillment(item.quotation, form)
    db.commit()
    return RedirectResponse(url=f"/design/items/{item_id}?products_saved=1", status_code=302)


@router.post("/items/{item_id}/designs")
async def design_upload_image(
    item_id: int,
    request: Request,
    design_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Diseñador/admin adjunta imagen de diseño (queda guardada en la cotización)."""
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    item = _load_item_for_access(db, item_id)
    if not item or not can_attach_design_images(user, item):
        return RedirectResponse(url="/design/pending", status_code=302)

    quotation = item.quotation
    if not quotation:
        return RedirectResponse(url=f"/design/items/{item_id}", status_code=302)

    try:
        sync_legacy_design_file(db, quotation)
        validate_upload_filename(design_file.filename)
        data = await read_upload_bytes(design_file, 10 * 1024 * 1024)
        add_design_image(db, quotation, data)
        try:
            add_design_observation(
                db,
                item_id,
                user=user,
                note=f"Adjuntó imagen de diseño: {design_file.filename or 'archivo'}",
            )
        except ValueError:
            db.commit()
        return RedirectResponse(
            url=f"/design/items/{item_id}?uploaded=1",
            status_code=302,
        )
    except (UploadValidationError, DesignLimitError, ValueError) as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/design/items/{item_id}?upload_error={quote(str(exc))}",
            status_code=302,
        )


@router.post("/items/{item_id}/designs/{design_id}/delete")
async def design_delete_image(
    item_id: int,
    design_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    item = _load_item_for_access(db, item_id)
    if not item or not can_attach_design_images(user, item):
        return RedirectResponse(url="/design/pending", status_code=302)

    quotation = item.quotation
    if not quotation:
        return RedirectResponse(url=f"/design/items/{item_id}", status_code=302)

    try:
        delete_design_image(db, quotation, design_id)
        try:
            add_design_observation(
                db,
                item_id,
                user=user,
                note="Eliminó una imagen de diseño",
            )
        except ValueError:
            db.commit()
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/design/items/{item_id}?upload_error={quote(str(exc))}",
            status_code=302,
        )

    return RedirectResponse(url=f"/design/items/{item_id}", status_code=302)





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





@router.post("/items/{item_id}/claim")
async def design_claim_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Diseñador se autoasigna una cotización/ítem disponible."""
    user = role_required(request, [ROLE_DISENADOR, ROLE_ADMIN])
    if isinstance(user, RedirectResponse):
        return user

    from urllib.parse import quote

    # Admin no se autoasigna; solo diseñadores
    if user.role != ROLE_DISENADOR:
        return RedirectResponse(
            url=f"/design/items/{item_id}?claim_error={quote('Solo diseñadores pueden autoasignarse.')}",
            status_code=302,
        )

    item = (
        db.query(QuotationItem)
        .options(joinedload(QuotationItem.quotation).joinedload(Quotation.production_order))
        .filter(QuotationItem.id == item_id)
        .first()
    )
    if not item or not can_view_design_item(user, item):
        return RedirectResponse(url="/design/pending?filter=available", status_code=302)

    if not can_self_assign_design_item(user, item):
        return RedirectResponse(
            url=f"/design/pending?filter=available&claim_error={quote('Esta cotización ya no está disponible.')}",
            status_code=302,
        )

    try:
        order = claim_design_item(db, item_id, user=user)
        return RedirectResponse(
            url=f"/design/items/{item_id}?claimed=1",
            status_code=302,
        )
    except ValueError as exc:
        return RedirectResponse(
            url=f"/design/pending?filter=available&claim_error={quote(str(exc))}",
            status_code=302,
        )


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
