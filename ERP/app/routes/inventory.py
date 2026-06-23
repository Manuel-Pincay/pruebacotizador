from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth.auth_handler import role_required
from app.database import get_db
from app.models.inventory_movement import InventoryMovement
from app.models.product import Product
from app.services.inventory_labels_service import (
    ALLOWED_QUANTITIES,
    find_product_by_code,
    generate_labels_pdf,
    normalize_label_quantity,
    search_products,
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
