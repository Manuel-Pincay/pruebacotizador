from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.auth.auth_handler import role_required
from app.database import get_db
from app.models.inventory_movement import InventoryMovement
from app.models.product import Product
from app.models.raw_material_movement import RawMaterialMovement
from app.services.inventory_labels_service import (
    ALLOWED_QUANTITIES,
    find_product_by_code,
    generate_labels_pdf,
    normalize_label_quantity,
    search_products,
)
from app.services.raw_material_service import (
    MATERIAL_KINDS,
    MATERIAL_TYPES,
    adjust_stock,
    count_low_stock,
    create_raw_material,
    get_raw_material,
    list_raw_materials,
    material_to_dict,
    materials_for_design,
)
from app.utils.context import get_global_config

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
)

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["inject_global_config"] = get_global_config

INVENTORY_ROLES = ["admin"]


def _require_inventory(request: Request):
    user = role_required(request, INVENTORY_ROLES)
    if isinstance(user, RedirectResponse):
        return user
    return user


@router.get("/", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db)):
    user = _require_inventory(request)
    if isinstance(user, RedirectResponse):
        return user

    movements = (
        db.query(InventoryMovement)
        .order_by(InventoryMovement.id.desc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="inventory/list.html",
        context={"movements": movements, "user": user},
    )


@router.get("/stock", response_class=HTMLResponse)
async def inventory_stock_page(request: Request, db: Session = Depends(get_db)):
    user = _require_inventory(request)
    if isinstance(user, RedirectResponse):
        return user

    products = (
        db.query(Product)
        .filter(Product.active.is_(True))
        .order_by(Product.name.asc())
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="inventory/stock.html",
        context={"products": products, "user": user},
    )


@router.get("/labels", response_class=HTMLResponse)
async def inventory_labels_page(
    request: Request,
    search: str = "",
    db: Session = Depends(get_db),
):
    user = _require_inventory(request)
    if isinstance(user, RedirectResponse):
        return user

    products = search_products(db, search=search)

    return templates.TemplateResponse(
        request=request,
        name="inventory/labels.html",
        context={
            "products": products,
            "search": search,
            "label_quantities": ALLOWED_QUANTITIES,
            "user": user,
        },
    )


@router.get("/labels/lookup")
async def inventory_labels_lookup(
    request: Request,
    code: str = "",
    db: Session = Depends(get_db),
):
    user = _require_inventory(request)
    if isinstance(user, RedirectResponse):
        return user

    product = find_product_by_code(db, code)
    if not product:
        return JSONResponse(
            status_code=404,
            content={"error": "Producto no encontrado"},
        )

    return {
        "id": product.id,
        "code": product.code,
        "name": product.name,
        "price": float(product.price or 0),
        "stock": int(product.stock or 0),
    }


@router.post("/labels/pdf")
async def inventory_labels_pdf(
    request: Request,
    db: Session = Depends(get_db),
):
    user = _require_inventory(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    product_ids = form.getlist("product_id")

    if not product_ids:
        return RedirectResponse(
            url="/inventory/labels?error=sin_seleccion",
            status_code=302,
        )

    items: list[tuple[Product, int]] = []
    skipped_without_code = 0

    for raw_id in product_ids:
        try:
            product_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            continue
        if not (product.code or "").strip():
            skipped_without_code += 1
            continue

        qty = normalize_label_quantity(form.get(f"qty_{product_id}"))
        items.append((product, qty))

    if not items:
        return RedirectResponse(
            url="/inventory/labels?error=sin_codigo",
            status_code=302,
        )

    pdf_buffer = generate_labels_pdf(items)
    filename = "etiquetas_productos.pdf"
    if skipped_without_code:
        filename = "etiquetas_productos_parcial.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


# ─── Materia prima ───────────────────────────────────────────────

MATERIALS_VIEW_ROLES = ["admin", "produccion", "disenador", "ventas"]


@router.get("/materials", response_class=HTMLResponse)
async def raw_materials_page(
    request: Request,
    kind: str = "",
    low: str = "",
    db: Session = Depends(get_db),
):
    user = _require_inventory(request)
    if isinstance(user, RedirectResponse):
        return user

    materials = list_raw_materials(
        db,
        kind=kind or None,
        active_only=True,
        low_stock_only=low == "1",
    )
    movements = (
        db.query(RawMaterialMovement)
        .options(joinedload(RawMaterialMovement.raw_material))
        .order_by(RawMaterialMovement.id.desc())
        .limit(30)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="inventory/materials.html",
        context={
            "user": user,
            "materials": materials,
            "movements": movements,
            "kinds": MATERIAL_KINDS,
            "material_types": MATERIAL_TYPES,
            "filter_kind": kind,
            "filter_low": low == "1",
            "low_stock_count": count_low_stock(db),
            "error": request.query_params.get("error", ""),
            "success": request.query_params.get("success", ""),
        },
    )


@router.post("/materials/create")
async def raw_materials_create(
    request: Request,
    kind: str = Form("plancha"),
    material_type: str = Form(""),
    name: str = Form(""),
    size: str = Form(""),
    thickness: str = Form(""),
    color: str = Form(""),
    stock: float = Form(0),
    min_stock: float = Form(0),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _require_inventory(request)
    if isinstance(user, RedirectResponse):
        return user
    try:
        create_raw_material(
            db,
            kind=kind,
            material_type=material_type,
            name=name,
            size=size,
            thickness=thickness,
            color=color,
            stock=stock,
            min_stock=min_stock,
            notes=notes,
            user_id=user.id,
        )
    except ValueError as exc:
        from urllib.parse import quote
        return RedirectResponse(
            url=f"/inventory/materials?error={quote(str(exc))}",
            status_code=302,
        )
    return RedirectResponse(url="/inventory/materials?success=created", status_code=302)


@router.post("/materials/{material_id}/adjust")
async def raw_materials_adjust(
    material_id: int,
    request: Request,
    movement_type: str = Form("entrada"),
    quantity: float = Form(0),
    reason: str = Form(""),
    db: Session = Depends(get_db),
):
    user = _require_inventory(request)
    if isinstance(user, RedirectResponse):
        return user
    material = get_raw_material(db, material_id)
    if not material:
        return RedirectResponse(url="/inventory/materials?error=no_encontrado", status_code=302)
    try:
        adjust_stock(
            db,
            material,
            quantity=quantity,
            movement_type=movement_type,
            reason=reason or ("Reabastecimiento" if movement_type == "entrada" else "Ajuste"),
            user_id=user.id,
        )
    except ValueError as exc:
        from urllib.parse import quote
        return RedirectResponse(
            url=f"/inventory/materials?error={quote(str(exc))}",
            status_code=302,
        )
    return RedirectResponse(url="/inventory/materials?success=adjusted", status_code=302)


@router.post("/materials/{material_id}/min-stock")
async def raw_materials_min_stock(
    material_id: int,
    request: Request,
    min_stock: float = Form(0),
    db: Session = Depends(get_db),
):
    user = _require_inventory(request)
    if isinstance(user, RedirectResponse):
        return user
    material = get_raw_material(db, material_id)
    if not material:
        return RedirectResponse(url="/inventory/materials?error=no_encontrado", status_code=302)
    material.min_stock = max(0, float(min_stock or 0))
    db.commit()
    return RedirectResponse(url="/inventory/materials?success=min_updated", status_code=302)


@router.get("/api/materials")
async def raw_materials_api(
    request: Request,
    design_material: str = "",
    db: Session = Depends(get_db),
):
    """Lista materia prima para formularios de producción/diseño."""
    user = role_required(request, MATERIALS_VIEW_ROLES)
    if isinstance(user, RedirectResponse):
        return JSONResponse(status_code=401, content={"error": "No autorizado"})
    materials = materials_for_design(db, design_material or None)
    return JSONResponse([material_to_dict(m) for m in materials])
