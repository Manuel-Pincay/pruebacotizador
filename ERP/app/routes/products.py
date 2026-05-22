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

from app.models.product import Product

from app.auth.auth_handler import login_required, role_required


# =====================================
# ROUTER
# =====================================

router = APIRouter(
    prefix="/products",
    tags=["products"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

UPLOAD_DIR = "uploads/products"


# =====================================
# PRODUCTS PAGE
# =====================================

@router.get(
    "/",
    response_class=HTMLResponse
)
async def products_page(
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin"]
    )

    if isinstance(user, RedirectResponse):
        return user

    products = db.query(Product).all()

    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            "products": products
        }
    )


# =====================================
# NEW PRODUCT PAGE
# =====================================

@router.get(
    "/new",
    response_class=HTMLResponse
)
async def new_product_page(request: Request):

    user = role_required(
        request,
        ["admin"]
    )

    if isinstance(user, RedirectResponse):
        return user

    return templates.TemplateResponse(
        request=request,
        name="product_new.html",
        context={}
    )



# =====================================
# SEARCH PRODUCTS API
# =====================================

@router.get("/search")
def search_products(
    q: str,
    db: Session = Depends(get_db)
):

    products = db.query(Product).filter(

        or_(

            Product.name.ilike(f"%{q}%"),

            Product.code.ilike(f"%{q}%"),

            Product.category.ilike(f"%{q}%")

        )

    ).order_by(

        Product.name.asc()

    ).limit(10).all()

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

        "logo": "Sí" if getattr(product, "custom", False) else "No"

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

    thickness: str = Form(""),
    price: float = Form(...),

    cost: float = Form(...),

    stock: int = Form(0),

    custom: str = Form("no"),

    image: UploadFile = File(None),

    db: Session = Depends(get_db)

):

    image_name = None

    # =====================================
    # SAVE IMAGE
    # =====================================

    if image and image.filename:

        os.makedirs(
            UPLOAD_DIR,
            exist_ok=True
        )

        extension = image.filename.split(".")[-1]

        image_name = f"{uuid.uuid4()}.{extension}"

        file_path = os.path.join(
            UPLOAD_DIR,
            image_name
        )

        with open(file_path, "wb") as buffer:

            shutil.copyfileobj(
                image.file,
                buffer
            )

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

        size=size,

        thickness=thickness,

        price=price,

        cost=cost,

        stock=stock,

        custom=True if custom == "yes" else False,
        

        image=image_name

    )

    db.add(product)

    db.commit()

    db.refresh(product)

    return RedirectResponse(

        url="/products",

        status_code=302

    )
# =====================================
    # editar PRODUCT
    # =====================================
@router.get(
    "/{product_id}/edit",
    response_class=HTMLResponse
)
async def edit_product_page(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    user = role_required(
        request,
        ["admin"]
    )

    if isinstance(user, RedirectResponse):
        return user

    product = db.query(
        Product
    ).filter(
        Product.id == product_id
    ).first()

    if not product:

        return RedirectResponse(
            url="/products",
            status_code=302
        )

    return templates.TemplateResponse(
        request=request,
        name="product_edit.html",
        context={
            "product": product
        }
    )

# =====================================
    # guardar editar PRODUCT
    # =====================================

@router.post("/{product_id}/edit")
async def update_product(

    product_id: int,

    code: str = Form(...),

    name: str = Form(...),

    description: str = Form(""),
    theme: str = Form(""),

    category: str = Form(""),

    material: str = Form(""),

    color: str = Form(""),

    size: str = Form(""),

    thickness: str = Form(""),

    price: float = Form(...),

    cost: float = Form(...),

    stock: int = Form(0),

    custom: str = Form("no"),

    db: Session = Depends(get_db)

):

    try:

        product = db.query(
            Product
        ).filter(
            Product.id == product_id
        ).first()

        if not product:

            return RedirectResponse(
                url="/products",
                status_code=302
            )

        product.code = code
        product.name = name
        product.description = description
        product.material = material
        product.theme = theme
        product.category = category
        product.material = material
        product.color = color
        product.size = size
        product.thickness = thickness
        product.price = price
        product.cost = cost
        product.stock = stock
        product.custom = True if custom == "yes" else False

        db.commit()

        return RedirectResponse(
            url="/products",
            status_code=302
        )

    except Exception as e:

        db.rollback()

        print(
            "ERROR UPDATE PRODUCT:",
            str(e)
        )

        return HTMLResponse(
            content=f"""
            <h1>
                Error actualizando producto
            </h1>

            <p>
                {str(e)}
            </p>
            """,
            status_code=500
        )
    # =====================================
    # ELIMINAR PRODUCT
    # =====================================
@router.get("/{product_id}/delete")
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db)
):

    try:

        product = db.query(
            Product
        ).filter(
            Product.id == product_id
        ).first()

        if product:

            db.delete(product)

            db.commit()

        return RedirectResponse(
            url="/products",
            status_code=302
        )

    except Exception as e:

        db.rollback()

        print(
            "ERROR DELETE PRODUCT:",
            str(e)
        )

        return HTMLResponse(
            content=f"""
            <h1>
                Error eliminando producto
            </h1>

            <p>
                {str(e)}
            </p>
            """,
            status_code=500
        )

@router.get("/api/list")
async def products_api(
    db: Session = Depends(get_db)
):

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
            "stock": product.stock
        }
        for product in products
    ]