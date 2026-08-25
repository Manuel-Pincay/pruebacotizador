from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth.auth_handler import role_required
from app.auth.design_permissions import (
    can_delete_design_order,
    can_edit_design_order,
    can_edit_fabrication_data,
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
    DESIGN_EDIT_STATUSES,
    DESIGN_MATERIALS,
    apply_quotation_item_fulfillment,
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
    normalize_status,
    parse_file_specs_from_form,
    quotation_needs_fabrication,
    transition_status,
    update_design_fields,
    work_items_payload,
)
from app.services.quotation_design_service import (
    MAX_QUOTATION_DESIGNS,
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


def _designs_payload(quotation: Quotation | None) -> list[dict]:
    if not quotation:
        return []
    rows = []
    for design in sorted(quotation.designs or [], key=lambda d: d.sort_order or 0):
        url = design_image_url(design.filename)
        if not url:
            continue
        rows.append({"id": design.id, "filename": design.filename, "url": url})
    return rows


def _order_form_context(
    db: Session,
    user,
    order_model,
    *,
    error: str = "",
    claimed: str = "",
    claim_error: str = "",
    upload_ok: str = "",
    upload_error: str = "",
):
    client = order_model.quotation.client if order_model.quotation else None
    order = build_order_dict(order_model, client_name=client.name if client else "—")
    work_items = work_items_payload(order_model.quotation)
    designs = _designs_payload(order_model.quotation)
    can_edit = can_edit_design_order(user, order_model)
    status = normalize_status(order_model.status)
    return {
        "user": user,
        "prefill": {
            "quotation_id": order["quotation_id"],
            "client_name": order["client_name"],
        },
        "order": order,
        "history": build_history_list(order_model),
        "can_edit": can_edit,
        "can_approve": can_edit and status in DESIGN_EDIT_STATUSES,
        "can_edit_fabrication": can_edit_fabrication_data(user, order_model)
        and quotation_needs_fabrication(order_model.quotation),
        "can_claim": can_self_assign_design_order(user, order_model),
        "can_reassign": can_reassign_design_order(user),
        "designers": list_designers(db) if is_design_admin(user) else [],
        "materials": DESIGN_MATERIALS,
        "sizes": list_design_sizes(db),
        "usb_references": list_usb_references(db),
        "work_items": work_items,
        "needs_fabrication": quotation_needs_fabrication(order_model.quotation),
        "designs": designs,
        "designs_count": len(designs),
        "max_designs": MAX_QUOTATION_DESIGNS,
        "error": error,
        "claimed": claimed,
        "claim_error": claim_error,
        "upload_ok": upload_ok,
        "upload_error": upload_error,
        "passed": "",
    }


@router.get("/orders", response_class=HTMLResponse)
async def design_orders_list(request: Request, db: Session = Depends(get_db)):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    rows = list_design_orders(
        db,
        viewer_user_id=None,
        admin_view=True,
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

    if order_model.quotation:
        sync_legacy_design_file(db, order_model.quotation)
        db.commit()

    ctx = _order_form_context(
        db,
        user,
        order_model,
        claimed=request.query_params.get("claimed", ""),
        claim_error=request.query_params.get("claim_error", ""),
        upload_ok=request.query_params.get("uploaded", ""),
        upload_error=request.query_params.get("upload_error", ""),
    )
    ctx["passed"] = request.query_params.get("passed", "")
    return templates.TemplateResponse(
        request=request,
        name="design/order_form.html",
        context=ctx,
    )


@router.post("/orders/{order_id}")
async def design_order_save(
    order_id: int,
    request: Request,
    material: str = Form(""),
    size: str = Form(""),
    usb_reference: str = Form(""),
    detail: str = Form(""),
    copies: int = Form(1),
    assigned_to_user_id: str = Form(""),
    use_fabrication_materials: str = Form("0"),
    action: str = Form("save"),
    db: Session = Depends(get_db),
):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    order_model = get_production_order(db, order_id)
    if not order_model or not can_view_design_order(user, order_model):
        return RedirectResponse(url="/design/orders", status_code=302)

    form = await request.form()
    file_specs = parse_file_specs_from_form(form)
    if can_edit_design_order(user, order_model):
        apply_quotation_item_fulfillment(order_model.quotation, form)

    needs_fab = quotation_needs_fabrication(order_model.quotation)
    use_fab = needs_fab and str(use_fabrication_materials or "0").strip() in ("1", "true", "on", "yes")
    from app.services.raw_material_service import parse_raw_material_items_from_form

    try:
        raw_items = parse_raw_material_items_from_form(form) if use_fab else None
    except ValueError as exc:
        order_model = get_production_order(db, order_id)
        return templates.TemplateResponse(
            request=request,
            name="design/order_form.html",
            context=_order_form_context(db, user, order_model, error=str(exc)),
            status_code=400,
        )

    try:
        if can_reassign_design_order(user) and assigned_to_user_id.strip().isdigit():
            assign_production_designer(db, order_model, int(assigned_to_user_id))
            order_model = get_production_order(db, order_id) or order_model

        if action == "approve":
            if not can_edit_design_order(user, order_model):
                raise ValueError("Sin permiso para enviar la orden.")
            if needs_fab:
                update_design_fields(
                    db, order_model,
                    file_specs=file_specs,
                    usb_reference=usb_reference, notes=detail, copies=copies, user=user,
                    use_fabrication_materials=use_fab,
                    raw_material_items=raw_items,
                )
            else:
                # Solo nota: sin datos de fabricación
                update_design_fields(
                    db, order_model,
                    notes=detail, copies=1, user=user,
                    use_fabrication_materials=False,
                )
            order_model = get_production_order(db, order_id) or order_model
            approve_design(
                db, order_model, user=user, notes=detail,
                use_fabrication_materials=use_fab if needs_fab else False,
                raw_material_items=raw_items if needs_fab and use_fab else None,
            )
            if not needs_fab:
                ship_url = (
                    f"/shipments/new/{order_model.quotation_id}?passed=shipping"
                    if order_model.quotation_id
                    else f"/design/orders/{order_id}?passed=shipping"
                )
                return RedirectResponse(url=ship_url, status_code=302)
            return RedirectResponse(
                url=f"/design/orders/{order_id}?passed=production",
                status_code=302,
            )
        elif can_edit_design_order(user, order_model):
            if needs_fab:
                update_design_fields(
                    db, order_model,
                    file_specs=file_specs,
                    usb_reference=usb_reference, notes=detail, copies=copies, user=user,
                    use_fabrication_materials=use_fab,
                    raw_material_items=raw_items,
                )
            else:
                update_design_fields(
                    db, order_model,
                    notes=detail, copies=1, user=user,
                    use_fabrication_materials=False,
                )
            db.commit()
    except ValueError as exc:
        order_model = get_production_order(db, order_id) or order_model
        return templates.TemplateResponse(
            request=request,
            name="design/order_form.html",
            context=_order_form_context(db, user, order_model, error=str(exc)),
            status_code=400,
        )

    return RedirectResponse(url=f"/design/orders/{order_id}", status_code=302)


@router.post("/orders/{order_id}/fabrication")
async def design_order_fabrication_save(
    order_id: int,
    request: Request,
    usb_reference: str = Form(""),
    detail: str = Form(""),
    copies: int = Form(1),
    use_fabrication_materials: str = Form("0"),
    db: Session = Depends(get_db),
):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    order_model = get_production_order(db, order_id)
    if not order_model or not can_view_design_order(user, order_model):
        return JSONResponse({"success": False, "message": "Orden no encontrada."}, status_code=404)

    if not can_edit_fabrication_data(user, order_model):
        return JSONResponse({"success": False, "message": "Sin permiso para editar estos datos."}, status_code=403)

    form = await request.form()
    file_specs = parse_file_specs_from_form(form)
    use_fab = str(use_fabrication_materials or "0").strip() in ("1", "true", "on", "yes")
    from app.services.raw_material_service import parse_raw_material_items_from_form

    try:
        raw_items = parse_raw_material_items_from_form(form) if use_fab else None
    except ValueError as exc:
        return JSONResponse({"success": False, "message": str(exc)}, status_code=400)

    try:
        update_design_fields(
            db,
            order_model,
            file_specs=file_specs,
            usb_reference=usb_reference,
            notes=detail,
            copies=copies,
            user=user,
            use_fabrication_materials=use_fab,
            raw_material_items=raw_items,
        )
        db.commit()
    except ValueError as exc:
        return JSONResponse({"success": False, "message": str(exc)}, status_code=400)

    return JSONResponse({"success": True})


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
    products = work_items_payload(order_model.quotation)
    pdf_buffer = export_design_sheet_pdf(order, products=products)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="orden_{order["order_label"]}.pdf"'},
    )


@router.post("/orders/{order_id}/designs")
async def design_order_upload_image(
    order_id: int,
    request: Request,
    design_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    order_model = get_production_order(db, order_id)
    if not order_model or not can_view_design_order(user, order_model):
        return RedirectResponse(url="/design/orders", status_code=302)
    if not can_edit_design_order(user, order_model):
        return RedirectResponse(url=f"/design/orders/{order_id}", status_code=302)

    quotation = order_model.quotation
    if not quotation:
        return RedirectResponse(url=f"/design/orders/{order_id}", status_code=302)

    try:
        sync_legacy_design_file(db, quotation)
        validate_upload_filename(design_file.filename)
        data = await read_upload_bytes(design_file, 10 * 1024 * 1024)
        add_design_image(db, quotation, data)
        db.commit()
        return RedirectResponse(url=f"/design/orders/{order_id}?uploaded=1", status_code=302)
    except (UploadValidationError, DesignLimitError, ValueError) as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/design/orders/{order_id}?upload_error={quote(str(exc))}",
            status_code=302,
        )


@router.post("/orders/{order_id}/designs/{design_id}/delete")
async def design_order_delete_image(
    order_id: int,
    design_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_design_access(request)
    if isinstance(user, RedirectResponse):
        return user

    order_model = get_production_order(db, order_id)
    if not order_model or not can_edit_design_order(user, order_model):
        return RedirectResponse(url="/design/orders", status_code=302)

    quotation = order_model.quotation
    if not quotation:
        return RedirectResponse(url=f"/design/orders/{order_id}", status_code=302)

    try:
        delete_design_image(db, quotation, design_id)
        db.commit()
    except ValueError:
        db.rollback()
    return RedirectResponse(url=f"/design/orders/{order_id}", status_code=302)
