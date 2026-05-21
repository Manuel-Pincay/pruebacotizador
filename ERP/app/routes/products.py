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

            "category": product.category or ""

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