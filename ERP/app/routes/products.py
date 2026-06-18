from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form
from fastapi import UploadFile
from fastapi import File

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db

from app.utils.activity import log_activity

from app.models.productcategory import ProductCategory
from app.models.productmaterial import ProductMaterial
from app.models.productcolor import ProductColor
from app.models.producttheme import ProductTheme
from app.models.productthickness import ProductThickness
from app.models.measurementunit import MeasurementUnit
from app.models.product import Product

from app.auth.auth_handler import role_required
from app.services.product_catalog_service import ensure_product_catalog_values
from app.utils.text_format import format_title_words
from app.utils.dialog_response import dialog_message_response
from app.utils.image_storage import (
    UploadValidationError,
    delete_product_files,
    product_image_url,
    read_upload_bytes,
    read_upload_bytes_sync,
    save_product_image,
    validate_upload_filename,
)

# =====================================
# ROUTER
# =====================================

router = APIRouter(prefix="/products", tags=["products"])

PRODUCT_VIEW_ROLES = ["admin", "ventas"]
PRODUCT_MANAGE_ROLES = ["admin", "ventas"]

templates = Jinja2Templates(directory="app/templates")

from app.utils.context import get_global_config

templates.env.globals["inject_global_config"] = get_global_config
templates.env.globals["product_image_url"] = product_image_url


# =====================================
# PRODUCTS PAGE
# =====================================


@router.get("/", response_class=HTMLResponse)
async def products_page(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, PRODUCT_VIEW_ROLES)

    if isinstance(user, RedirectResponse):
        return user

    products = db.query(Product).order_by(Product.name.asc()).all()

    total_products = len(products)
    out_of_stock = sum(1 for p in products if (p.stock or 0) <= 0)
    low_stock = sum(1 for p in products if 0 < (p.stock or 0) <= 5)
    custom_count = sum(1 for p in products if p.custom)

    return templates.TemplateResponse(
        request=request,
        name="products/list.html",
        context={
            "products": products,
            "user": user,
            "total_products": total_products,
            "out_of_stock": out_of_stock,
            "low_stock": low_stock,
            "custom_count": custom_count,
            "is_admin": user.role == "admin",
            "can_manage_products": user.role in PRODUCT_MANAGE_ROLES,
        },
    )


# =====================================
# NEW PRODUCT PAGE
# =====================================


@router.get("/new", response_class=HTMLResponse)
async def new_product_page(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, ["admin"])

    if isinstance(user, RedirectResponse):
        return user

    categories = db.query(ProductCategory).all()

    materials = db.query(ProductMaterial).all()

    colors = db.query(ProductColor).all()

    themes = db.query(ProductTheme).all()

    thicknesses = db.query(ProductThickness).all()

    units = db.query(MeasurementUnit).all()

    return templates.TemplateResponse(
        request=request,
        name="products/new.html",
        context={
            "categories": categories,
            "materials": materials,
            "colors": colors,
            "themes": themes,
            "thicknesses": thicknesses,
            "units": units,
        },
    )


# =====================================
# SEARCH PRODUCTS API
# =====================================


@router.get("/search")
def search_products(request: Request, q: str, db: Session = Depends(get_db)):

    user = role_required(request, PRODUCT_VIEW_ROLES)
    if isinstance(user, RedirectResponse):
        return user

    products = (
        db.query(Product)
        .filter(
            or_(
                Product.name.ilike(f"%{q}%"),
                Product.code.ilike(f"%{q}%"),
                Product.category.ilike(f"%{q}%"),
            )
        )
        .order_by(Product.name.asc())
        .limit(10)
        .all()
    )

    return [
        {
            "id": product.id,
            "code": product.code,
            "name": product.name,
            "price": float(product.price or 0),
            "stock": float(product.stock or 0),
            "category": product.category or "",
            "measure": product.size or "",
            "theme": product.theme or "",
            "color": product.color or "",
        }
        for product in products
    ]


# =====================================
# CREATE PRODUCT
# =====================================


@router.post("/new")
async def create_product(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form(""),
    theme: str = Form(""),
    material: str = Form(""),
    color: str = Form(""),
    size: str = Form(""),
    size_unit: str = Form(""),
    thickness: str = Form(""),
    price: float = Form(...),
    cost: float = Form(...),
    stock: int = Form(0),
    custom: str = Form("no"),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user

    formatted_size = ""

    if size:

        formatted_size = f"{size} {size_unit}"

    existing_product = db.query(Product).filter(Product.code == code).first()

    if existing_product:

        return dialog_message_response(
            f"Ya existe un producto con el código {code}",
            dialog_type="warning",
            title="Código duplicado",
        )
    image_name = None

    if image and image.filename:
        try:
            validate_upload_filename(image.filename)
            data = read_upload_bytes_sync(image, 5 * 1024 * 1024)
            image_name = save_product_image(data)
        except UploadValidationError as exc:
            return dialog_message_response(
                str(exc),
                dialog_type="warning",
                title="Imagen no válida",
            )

    catalog = ensure_product_catalog_values(
        db,
        category=category,
        theme=theme,
        material=material,
        color=color,
    )

    product = Product(
        code=(code or "").strip(),
        name=format_title_words(name),
        description=(description or "").strip(),
        theme=catalog["theme"],
        category=catalog["category"],
        material=catalog["material"],
        color=catalog["color"],
        size=formatted_size,
        thickness=thickness,
        price=price,
        cost=cost,
        stock=stock,
        custom=True if custom == "yes" else False,
        image=image_name,
    )

    db.add(product)

    db.commit()

    db.refresh(product)

    try:
        log_activity(
            db,
            "Producto creado",
            product.name or "Producto"
        )
    except Exception:
        pass

    return RedirectResponse(url="/products", status_code=302)


# =====================================
# EDIT PRODUCT PAGE
# =====================================


@router.get("/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_page(
    product_id: int, request: Request, db: Session = Depends(get_db)
):

    user = role_required(request, PRODUCT_MANAGE_ROLES)

    if isinstance(user, RedirectResponse):
        return user

    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:

        return RedirectResponse(url="/products", status_code=302)

    categories = db.query(ProductCategory).all()

    materials = db.query(ProductMaterial).all()

    colors = db.query(ProductColor).all()

    themes = db.query(ProductTheme).all()

    thicknesses = db.query(ProductThickness).all()

    units = db.query(MeasurementUnit).all()

    return templates.TemplateResponse(
        request=request,
        name="products/edit.html",
        context={
            "product": product,
            "categories": categories,
            "materials": materials,
            "colors": colors,
            "themes": themes,
            "thicknesses": thicknesses,
            "units": units,
            "user": user,
            "saved": request.query_params.get("saved") == "1",
            "error": request.query_params.get("error"),
        },
    )


# =====================================
# SAVE EDIT PRODUCT
# =====================================


@router.post("/{product_id}/edit")
async def update_product(
    request: Request,
    product_id: int,
    code: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form(""),
    theme: str = Form(""),
    material: str = Form(""),
    color: str = Form(""),
    size: str = Form(""),
    size_unit: str = Form(""),
    thickness: str = Form(""),
    price: float = Form(...),
    cost: float = Form(...),
    stock: int = Form(0),
    custom: str = Form("no"),
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
):

    user = role_required(request, PRODUCT_MANAGE_ROLES)
    if isinstance(user, RedirectResponse):
        return user

    edit_url = f"/products/{product_id}/edit"

    try:

        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:

            return RedirectResponse(url="/products", status_code=302)

        code = (code or "").strip()
        name = (name or "").strip()

        if not code or not name:
            return RedirectResponse(
                url=f"{edit_url}?error=campos",
                status_code=302,
            )

        # ==========================
        # VALIDATE DUPLICATE CODE
        # ==========================

        existing_product = (
            db.query(Product)
            .filter(Product.code == code, Product.id != product_id)
            .first()
        )

        if existing_product:

            return RedirectResponse(
                url=f"{edit_url}?error=code",
                status_code=302,
            )

        # ==========================
        # FORMAT SIZE
        # ==========================

        formatted_size = size

        if size and size_unit:

            formatted_size = f"{size} {size_unit}"

        # ==========================
        # IMAGE
        # ==========================

        if image and image.filename:
            try:
                validate_upload_filename(image.filename)
                data = await read_upload_bytes(image, 5 * 1024 * 1024)
                image_name = save_product_image(data)
                if product.image:
                    delete_product_files(product.image)
                product.image = image_name
            except UploadValidationError:
                return RedirectResponse(
                    url=f"{edit_url}?error=imagen",
                    status_code=302,
                )

        # ==========================
        # UPDATE PRODUCT
        # ==========================

        product.code = code

        product.name = format_title_words(name)

        product.description = (description or "").strip()

        catalog = ensure_product_catalog_values(
            db,
            category=category,
            theme=theme,
            material=material,
            color=color,
        )

        product.category = catalog["category"]

        product.theme = catalog["theme"]

        product.material = catalog["material"]

        product.color = catalog["color"]

        product.size = formatted_size

        product.thickness = thickness

        product.price = price

        product.cost = cost

        product.stock = stock

        product.custom = True if custom == "yes" else False

        db.commit()

        try:
            log_activity(
                db,
                "Producto actualizado",
                product.name or "Producto",
            )
        except Exception:
            pass

        return RedirectResponse(url=f"{edit_url}?saved=1", status_code=302)

    except Exception as e:

        db.rollback()

        print("ERROR UPDATE PRODUCT:", str(e))

        return RedirectResponse(
            url=f"{edit_url}?error=guardar",
            status_code=302,
        )

    # =====================================
    # ELIMINAR PRODUCT
    # =====================================


@router.get("/{product_id}/delete")
async def delete_product(
    request: Request, product_id: int, db: Session = Depends(get_db)
):

    user = role_required(request, PRODUCT_MANAGE_ROLES)
    if isinstance(user, RedirectResponse):
        return user

    try:

        product = db.query(Product).filter(Product.id == product_id).first()

        if product:
            image_name = product.image
            db.delete(product)
            db.commit()
            delete_product_files(image_name)

        return RedirectResponse(url="/products", status_code=302)

    except Exception as e:

        db.rollback()

        print("ERROR DELETE PRODUCT:", str(e))

        return HTMLResponse(
            content=f"""
            <h1>
                Error eliminando producto
            </h1>

            <p>
                {str(e)}
            </p>
            """,
            status_code=500,
        )


@router.get("/api/list")
async def products_api(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, PRODUCT_VIEW_ROLES)
    if isinstance(user, RedirectResponse):
        return user

    products = db.query(Product).all()

    return [
        {
            "id": product.id,
            "name": product.name,
            "theme": product.theme,
            "material": product.material,
            "color": product.color,
            "size": product.size,
            "price": product.price,
            "stock": product.stock,
        }
        for product in products
    ]

# CATALOGO
@router.get("/catalog/modal")
async def catalog_modal(
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(request, PRODUCT_VIEW_ROLES)
    if isinstance(user, RedirectResponse):
        return user

    products = (
        db.query(Product)
        .order_by(Product.name.asc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/products/catalog_table.html",
        context={
            "products": products
        }
    )

@router.get("/{product_id}/json")
async def product_json(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db)
):

    user = role_required(request, PRODUCT_VIEW_ROLES)
    if isinstance(user, RedirectResponse):
        return user

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .first()
    )

    if not product:
        return {"error": "Producto no encontrado"}

    return {
        "id": product.id,
        "name": product.name,
        "code": product.code,
        "price": float(product.price or 0),
        "stock": float(product.stock or 0),
        "measure": product.size or "",
        "theme": product.theme or "",
        "color": product.color or "",
    }