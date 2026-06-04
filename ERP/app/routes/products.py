import os
import shutil
import uuid

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

from app.auth.auth_handler import login_required, role_required

# =====================================
# ROUTER
# =====================================

router = APIRouter(prefix="/products", tags=["products"])

templates = Jinja2Templates(directory="app/templates")

from app.utils.context import get_global_config

templates.env.globals["inject_global_config"] = get_global_config

UPLOAD_DIR = "uploads/products"


# =====================================
# PRODUCTS PAGE
# =====================================


@router.get("/", response_class=HTMLResponse)
async def products_page(request: Request, db: Session = Depends(get_db)):

    user = role_required(request, ["admin", "ventas"])

    if isinstance(user, RedirectResponse):
        return user

    products = db.query(Product).all()

    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={"products": products, "user": user},
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
        name="product_new.html",
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
def search_products(q: str, db: Session = Depends(get_db)):

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
            "logo": "Sí" if getattr(product, "custom", False) else "No",
        }
        for product in products
    ]


# =====================================
# CREATE PRODUCT
# =====================================


@router.post("/new")
async def create_product(
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
    formatted_size = ""

    if size:

        formatted_size = f"{size} {size_unit}"

    existing_product = db.query(Product).filter(Product.code == code).first()

    if existing_product:

        return HTMLResponse(
            content=f"""
        <script>

            alert(
                'Ya existe un producto con el código {code}'
            )

            window.history.back()

        </script>
        """,
            status_code=400,
        )
    image_name = None

    # =====================================
    # SAVE IMAGE
    # =====================================

    if image and image.filename:

        os.makedirs(UPLOAD_DIR, exist_ok=True)

        extension = image.filename.split(".")[-1]

        image_name = f"{uuid.uuid4()}.{extension}"

        file_path = os.path.join(UPLOAD_DIR, image_name)

        with open(file_path, "wb") as buffer:

            shutil.copyfileobj(image.file, buffer)

    # =====================================
    # CREATE PRODUCT
    # =====================================

    product = Product(
        code=code,
        name=name,
        description=description,
        theme=theme,
        category=category,
        material=material,
        color=color,
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

    user = role_required(request, ["admin"])

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
        name="product_edit.html",
        context={
            "product": product,
            "categories": categories,
            "materials": materials,
            "colors": colors,
            "themes": themes,
            "thicknesses": thicknesses,
            "units": units,
        },
    )


# =====================================
# SAVE EDIT PRODUCT
# =====================================


@router.post("/{product_id}/edit")
async def update_product(
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
    db: Session = Depends(get_db),
):

    try:

        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:

            return RedirectResponse(url="/products", status_code=302)

        # ==========================
        # VALIDATE DUPLICATE CODE
        # ==========================

        existing_product = (
            db.query(Product)
            .filter(Product.code == code, Product.id != product_id)
            .first()
        )

        if existing_product:

            return HTMLResponse(
                content=f"""
                <script>

                    alert(
                        'Ya existe un producto con el código {code}'
                    );

                    window.history.back();

                </script>
                """,
                status_code=400,
            )

        # ==========================
        # FORMAT SIZE
        # ==========================

        formatted_size = size

        if size and size_unit:

            formatted_size = f"{size} {size_unit}"

        # ==========================
        # UPDATE PRODUCT
        # ==========================

        product.code = code

        product.name = name

        product.description = description

        product.category = category

        product.theme = theme

        product.material = material

        product.color = color

        product.size = formatted_size

        product.thickness = thickness

        product.price = price

        product.cost = cost

        product.stock = stock

        product.custom = True if custom == "yes" else False

        db.commit()

        return RedirectResponse(url="/products", status_code=302)

    except Exception as e:

        db.rollback()

        print("ERROR UPDATE PRODUCT:", str(e))

        return HTMLResponse(
            content=f"""
            <h1>
                Error actualizando producto
            </h1>

            <p>
                {str(e)}
            </p>
            """,
            status_code=500,
        )

    # =====================================
    # ELIMINAR PRODUCT
    # =====================================


@router.get("/{product_id}/delete")
async def delete_product(product_id: int, db: Session = Depends(get_db)):

    try:

        product = db.query(Product).filter(Product.id == product_id).first()

        if product:

            db.delete(product)

            db.commit()

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
async def products_api(db: Session = Depends(get_db)):

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

    products = (
        db.query(Product)
        .order_by(Product.name.asc())
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/catalog_table.html",
        context={
            "products": products
        }
    )

@router.get("/{product_id}/json")
async def product_json(
    product_id: int,
    db: Session = Depends(get_db)
):

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
        "logo": getattr(product, "logo", False)
    }