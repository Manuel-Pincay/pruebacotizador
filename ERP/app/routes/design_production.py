from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth.auth_handler import role_required
from app.auth.design_permissions import (
    can_delete_design_order,
    can_edit_design_order,
    can_export_design_orders,
    can_reassign_design_order,
    can_self_assign_design_order,
    can_view_design_item,
    can_view_design_order,
    is_design_admin,
)
from app.auth.permissions import ROLE_ADMIN, ROLE_DISENADOR
from app.database import get_db
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.services.design_catalog_service import list_design_sizes, list_usb_references
from app.services.design_service import list_designers
from app.services.production_order_service import (
    DESIGN_MATERIALS,
    approve_design,
    assign_designer as assign_production_designer,
    build_history_list,
    build_order_dict,
    claim_design_order,
    ensure_production_order,
    export_design_sheet_pdf,
    get_production_order,
    get_production_order_by_quotation,
    list_design_orders,
    transition_status,
    update_design_fields,
)
from app.utils.context import get_global_config

router = APIRouter(tags=["design-production"])
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["inject_global_config"] = get_global_config

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


@router.get("/orders", response_class=HTMLResponse)
async def design_orders_list(request: Request, db: Session = Depends(get_db)):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    rows = list_design_orders(
        db,
        viewer_user_id=user.id if user.role == ROLE_DISENADOR else None,
        admin_view=is_design_admin(user),
    )
    for row in rows:
        order_model = get_production_order(db, row["id"])
        row["can_edit"] = bool(order_model and can_edit_design_order(user, order_model))
        row["can_claim"] = bool(order_model and can_self_assign_design_order(user, order_model))

    return templates.TemplateResponse(
        request=request,
        name="design/orders.html",
        context={
            "user": user,
            "rows": rows,
            "can_delete": can_delete_design_order(user),
            "can_export": can_export_design_orders(user),
            "claim_error": request.query_params.get("claim_error", ""),
            "claimed": request.query_params.get("claimed", ""),
        },
    )


@router.post("/orders/{order_id}/claim")
async def design_claim_order(order_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user
    from urllib.parse import quote

    if user.role != ROLE_DISENADOR:
        return RedirectResponse(
            url=f"/design/orders?claim_error={quote('Solo diseñadores pueden autoasignarse.')}",
            status_code=302,
        )
    order = get_production_order(db, order_id)
    if not order or not can_view_design_order(user, order):
        return RedirectResponse(url="/design/orders", status_code=302)
    try:
        claim_design_order(db, order, user=user)
        return RedirectResponse(url=f"/design/orders/{order_id}?claimed=1", status_code=302)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/design/orders?claim_error={quote(str(exc))}",
            status_code=302,
        )


@router.get("/orders/for-item/{item_id}")
async def design_order_for_item(item_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    item = _load_item_for_access(db, item_id)
    if not item or not can_view_design_item(user, item):
        return RedirectResponse(url="/design/pending", status_code=302)

    quotation = db.query(Quotation).filter(Quotation.id == item.quotation_id).first()
    if not quotation:
        return RedirectResponse(url="/design/pending", status_code=302)

    order = get_production_order_by_quotation(db, quotation.id) or ensure_production_order(
        db, quotation, user_id=user.id
    )
    db.commit()
    if not order:
        return RedirectResponse(url="/design/pending", status_code=302)
    return RedirectResponse(url=f"/design/orders/{order.id}", status_code=302)


@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def design_order_detail(order_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    order_model = get_production_order(db, order_id)
    if not order_model or not can_view_design_order(user, order_model):
        return RedirectResponse(url="/design/orders", status_code=302)

    client = order_model.quotation.client if order_model.quotation else None
    order = build_order_dict(order_model, client_name=client.name if client else "—")

    return templates.TemplateResponse(
        request=request,
        name="design/order_form.html",
        context={
            "user": user,
            "prefill": {
                "quotation_id": order["quotation_id"],
                "client_name": order["client_name"],
            },
            "order": order,
            "history": build_history_list(order_model),
            "can_edit": can_edit_design_order(user, order_model),
            "can_claim": can_self_assign_design_order(user, order_model),
            "can_reassign": can_reassign_design_order(user),
            "designers": list_designers(db) if is_design_admin(user) else [],
            "materials": DESIGN_MATERIALS,
            "sizes": list_design_sizes(db),
            "usb_references": list_usb_references(db),
            "claimed": request.query_params.get("claimed", ""),
            "claim_error": request.query_params.get("claim_error", ""),
        },
    )


@router.post("/orders/{order_id}")
async def design_order_save(
    order_id: int,
    request: Request,
    file_name: str = Form(""),
    material: str = Form(""),
    size: str = Form(""),
    usb_reference: str = Form(""),
    detail: str = Form(""),
    copies: int = Form(1),
    assigned_to_user_id: str = Form(""),
    use_fabrication_materials: str = Form("0"),
    raw_material_id: str = Form(""),
    raw_material_qty: str = Form(""),
    action: str = Form("save"),
    db: Session = Depends(get_db),
):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    order_model = get_production_order(db, order_id)
    if not order_model or not can_view_design_order(user, order_model):
        return RedirectResponse(url="/design/orders", status_code=302)

    use_fab = str(use_fabrication_materials or "0").strip() in ("1", "true", "on", "yes")
    rm_id = int(raw_material_id) if str(raw_material_id or "").strip().isdigit() else None
    from app.services.raw_material_service import parse_raw_material_qty

    try:
        rm_qty = parse_raw_material_qty(raw_material_qty) if use_fab else None
    except ValueError as exc:
        order_model = get_production_order(db, order_id)
        client = order_model.quotation.client if order_model and order_model.quotation else None
        order = build_order_dict(order_model, client_name=client.name if client else "—") if order_model else {}
        return templates.TemplateResponse(
            request=request,
            name="design/order_form.html",
            context={
                "user": user,
                "prefill": {"quotation_id": order.get("quotation_id"), "client_name": order.get("client_name")},
                "order": order,
                "history": build_history_list(order_model) if order_model else [],
                "can_edit": True,
                "can_reassign": can_reassign_design_order(user),
                "designers": list_designers(db) if is_design_admin(user) else [],
                "materials": DESIGN_MATERIALS,
                "sizes": list_design_sizes(db),
                "usb_references": list_usb_references(db),
                "error": str(exc),
            },
            status_code=400,
        )

    try:
        if can_reassign_design_order(user) and assigned_to_user_id.strip().isdigit():
            assign_production_designer(db, order_model, int(assigned_to_user_id))
            order_model = get_production_order(db, order_id) or order_model

        if action == "approve":
            if not can_edit_design_order(user, order_model):
                raise ValueError("Sin permiso para enviar a producción.")
            update_design_fields(
                db, order_model,
                file_name=file_name, material=material, size=size,
                usb_reference=usb_reference, notes=detail, copies=copies, user=user,
                use_fabrication_materials=use_fab,
                raw_material_id=rm_id,
                raw_material_qty=rm_qty,
            )
            order_model = get_production_order(db, order_id) or order_model
            approve_design(
                db, order_model, user=user,
                use_fabrication_materials=use_fab,
                raw_material_id=rm_id,
                raw_material_qty=rm_qty,
            )
        elif can_edit_design_order(user, order_model):
            update_design_fields(
                db, order_model,
                file_name=file_name, material=material, size=size,
                usb_reference=usb_reference, notes=detail, copies=copies, user=user,
                use_fabrication_materials=use_fab,
                raw_material_id=rm_id,
                raw_material_qty=rm_qty,
            )
    except ValueError as exc:
        client = order_model.quotation.client if order_model.quotation else None
        order = build_order_dict(order_model, client_name=client.name if client else "—")
        return templates.TemplateResponse(
            request=request,
            name="design/order_form.html",
            context={
                "user": user,
                "prefill": {"quotation_id": order["quotation_id"], "client_name": order["client_name"]},
                "order": order,
                "history": build_history_list(order_model),
                "can_edit": True,
                "can_reassign": can_reassign_design_order(user),
                "designers": list_designers(db) if is_design_admin(user) else [],
                "materials": DESIGN_MATERIALS,
                "sizes": list_design_sizes(db),
                "usb_references": list_usb_references(db),
                "error": str(exc),
            },
            status_code=400,
        )

    return RedirectResponse(url=f"/design/orders/{order_id}", status_code=302)


@router.post("/orders/{order_id}/delete")
async def design_order_cancel(order_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user
    if not can_delete_design_order(user):
        return RedirectResponse(url="/design/orders", status_code=302)

    order_model = get_production_order(db, order_id)
    if order_model:
        transition_status(db, order_model, "cancelado", user=user, notes="Orden cancelada.", force=True)
    return RedirectResponse(url="/design/orders", status_code=302)


@router.get("/orders/{order_id}/print")
async def design_order_print(order_id: int, request: Request, db: Session = Depends(get_db)):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    order_model = get_production_order(db, order_id)
    if not order_model or not can_view_design_order(user, order_model):
        return RedirectResponse(url="/design/orders", status_code=302)

    client = order_model.quotation.client if order_model.quotation else None
    order = build_order_dict(order_model, client_name=client.name if client else "—")
    pdf_buffer = export_design_sheet_pdf(order)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="orden_{order["order_label"]}.pdf"'},
    )
