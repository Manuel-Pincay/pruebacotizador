from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form

from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.auth_handler import role_required

from app.models.productcategory import ProductCategory
from app.models.productmaterial import ProductMaterial
from app.models.productcolor import ProductColor
from app.models.producttheme import ProductTheme
from app.models.productthickness import ProductThickness
from app.models.measurementunit import MeasurementUnit
from app.services.catalog_seed import seed_product_catalogs

router = APIRouter(prefix="/product-settings", tags=["product_settings"])

templates = Jinja2Templates(directory="app/templates")

from app.utils.context import get_global_config

templates.env.globals["inject_global_config"] = get_global_config


class CatalogItemCreate(BaseModel):
    name: str


def _require_admin(request: Request):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    return user


def _api_create_catalog_item(
    request: Request,
    db: Session,
    model,
    name: str,
):
    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return JSONResponse({"ok": False, "error": "No autorizado"}, status_code=401)

    cleaned = name.strip()
    if not cleaned:
        return JSONResponse({"ok": False, "error": "El nombre no puede estar vacío"}, status_code=400)

    existing = db.query(model).filter(model.name == cleaned).first()
    if existing:
        return {"ok": True, "name": existing.name, "id": existing.id, "created": False}

    item = model(name=cleaned)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"ok": True, "name": item.name, "id": item.id, "created": True}


@router.post("/api/category")
async def api_create_category(
    request: Request,
    body: CatalogItemCreate,
    db: Session = Depends(get_db),
):
    return _api_create_catalog_item(request, db, ProductCategory, body.name)


@router.post("/api/material")
async def api_create_material(
    request: Request,
    body: CatalogItemCreate,
    db: Session = Depends(get_db),
):
    return _api_create_catalog_item(request, db, ProductMaterial, body.name)


@router.post("/api/color")
async def api_create_color(
    request: Request,
    body: CatalogItemCreate,
    db: Session = Depends(get_db),
):
    return _api_create_catalog_item(request, db, ProductColor, body.name)


@router.post("/api/theme")
async def api_create_theme(
    request: Request,
    body: CatalogItemCreate,
    db: Session = Depends(get_db),
):
    return _api_create_catalog_item(request, db, ProductTheme, body.name)


@router.post("/api/thickness")
async def api_create_thickness(
    request: Request,
    body: CatalogItemCreate,
    db: Session = Depends(get_db),
):
    return _api_create_catalog_item(request, db, ProductThickness, body.name)


@router.get("/", response_class=HTMLResponse)
async def product_settings_page(request: Request, db: Session = Depends(get_db)):

    user = _require_admin(request)
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
        name="products/settings.html",
        context={
            "categories": categories,
            "materials": materials,
            "colors": colors,
            "themes": themes,
            "thicknesses": thicknesses,
            "units": units,
            "user": user,
            "total_items": (
                len(categories) + len(materials) + len(colors)
                + len(themes) + len(thicknesses) + len(units)
            ),
        },
    )


# =====================================
# CREATE CATEGORY
# =====================================


@router.post("/category/new")
async def create_category(request: Request, name: str = Form(...), db: Session = Depends(get_db)):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    exists = db.query(ProductCategory).filter(ProductCategory.name == name).first()

    if not exists:

        db.add(ProductCategory(name=name))

        db.commit()

    return RedirectResponse("/product-settings", status_code=302)


# =====================================
# DELETE CATEGORY
# =====================================


@router.get("/category/{category_id}/delete")
async def delete_category(request: Request, category_id: int, db: Session = Depends(get_db)):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    category = (
        db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    )

    if category:

        db.delete(category)

        db.commit()

    return RedirectResponse("/product-settings", status_code=302)


@router.get("/init")
async def initialize_catalogs(request: Request, db: Session = Depends(get_db)):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    seed_product_catalogs(db)

    return RedirectResponse("/product-settings", status_code=302)

@router.post("/material/new")
async def create_material(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    exists = db.query(
        ProductMaterial
    ).filter(
        ProductMaterial.name == name
    ).first()

    if not exists:

        db.add(
            ProductMaterial(
                name=name
            )
        )

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )


@router.get("/material/{material_id}/delete")
async def delete_material(
    request: Request,
    material_id: int,
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    material = db.query(
        ProductMaterial
    ).filter(
        ProductMaterial.id == material_id
    ).first()

    if material:

        db.delete(material)

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )


# =====================================
# CREATE COLOR
# =====================================


@router.post("/color/new")
async def create_color(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    exists = db.query(
        ProductColor
    ).filter(
        ProductColor.name == name
    ).first()

    if not exists:

        db.add(
            ProductColor(
                name=name
            )
        )

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )


# =====================================
# DELETE COLOR
# =====================================


@router.get("/color/{color_id}/delete")
async def delete_color(
    request: Request,
    color_id: int,
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    color = db.query(
        ProductColor
    ).filter(
        ProductColor.id == color_id
    ).first()

    if color:

        db.delete(color)

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )


# =====================================
# CREATE THEME
# =====================================


@router.post("/theme/new")
async def create_theme(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    exists = db.query(
        ProductTheme
    ).filter(
        ProductTheme.name == name
    ).first()

    if not exists:

        db.add(
            ProductTheme(
                name=name
            )
        )

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )


# =====================================
# DELETE THEME
# =====================================


@router.get("/theme/{theme_id}/delete")
async def delete_theme(
    request: Request,
    theme_id: int,
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    theme = db.query(
        ProductTheme
    ).filter(
        ProductTheme.id == theme_id
    ).first()

    if theme:

        db.delete(theme)

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )


# =====================================
# CREATE THICKNESS
# =====================================


@router.post("/thickness/new")
async def create_thickness(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    exists = db.query(
        ProductThickness
    ).filter(
        ProductThickness.name == name
    ).first()

    if not exists:

        db.add(
            ProductThickness(
                name=name
            )
        )

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )


# =====================================
# DELETE THICKNESS
# =====================================


@router.get("/thickness/{thickness_id}/delete")
async def delete_thickness(
    request: Request,
    thickness_id: int,
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    thickness = db.query(
        ProductThickness
    ).filter(
        ProductThickness.id == thickness_id
    ).first()

    if thickness:

        db.delete(thickness)

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )


# =====================================
# CREATE UNIT
# =====================================


@router.post("/unit/new")
async def create_unit(
    request: Request,
    name: str = Form(...),
    abbreviation: str = Form(...),
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    exists = db.query(
        MeasurementUnit
    ).filter(
        MeasurementUnit.abbreviation == abbreviation
    ).first()

    if not exists:

        db.add(
            MeasurementUnit(
                name=name,
                abbreviation=abbreviation
            )
        )

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )


# =====================================
# DELETE UNIT
# =====================================


@router.get("/unit/{unit_id}/delete")
async def delete_unit(
    request: Request,
    unit_id: int,
    db: Session = Depends(get_db)
):

    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return user

    unit = db.query(
        MeasurementUnit
    ).filter(
        MeasurementUnit.id == unit_id
    ).first()

    if unit:

        db.delete(unit)

        db.commit()

    return RedirectResponse(
        "/product-settings",
        status_code=302
    )