from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form

from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.auth_handler import role_required

from app.models.productcategory import ProductCategory
from app.models.productmaterial import ProductMaterial
from app.models.productcolor import ProductColor
from app.models.producttheme import ProductTheme
from app.models.productthickness import ProductThickness
from app.models.measurementunit import MeasurementUnit

router = APIRouter(prefix="/product-settings", tags=["product_settings"])

templates = Jinja2Templates(directory="app/templates")

from app.utils.context import get_global_config
from app.utils.text_format import format_title_words

templates.env.globals["inject_global_config"] = get_global_config


def _require_admin(request: Request):
    user = role_required(request, ["admin"])
    if isinstance(user, RedirectResponse):
        return user
    return user


def _create_catalog_item_json(request: Request, db: Session, model, name: str):
    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return JSONResponse(status_code=401, content={"success": False, "message": "No autorizado."})

    cleaned = format_title_words(name)
    if not cleaned:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Ingresa un nombre válido."},
        )

    existing = (
        db.query(model)
        .filter(func.lower(model.name) == cleaned.lower())
        .first()
    )
    if existing:
        return {"success": True, "name": existing.name, "value": existing.name, "label": existing.name, "created": False}

    db.add(model(name=cleaned))
    db.commit()
    return {"success": True, "name": cleaned, "value": cleaned, "label": cleaned, "created": True}


def _create_thickness_json(request: Request, db: Session, name: str):
    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return JSONResponse(status_code=401, content={"success": False, "message": "No autorizado."})

    cleaned = " ".join((name or "").split())
    if not cleaned:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Ingresa un grosor válido."},
        )

    existing = (
        db.query(ProductThickness)
        .filter(func.lower(ProductThickness.name) == cleaned.lower())
        .first()
    )
    if existing:
        return {"success": True, "name": existing.name, "value": existing.name, "label": existing.name, "created": False}

    db.add(ProductThickness(name=cleaned))
    db.commit()
    return {"success": True, "name": cleaned, "value": cleaned, "label": cleaned, "created": True}


def _create_unit_json(request: Request, db: Session, name: str, abbreviation: str):
    user = _require_admin(request)
    if isinstance(user, RedirectResponse):
        return JSONResponse(status_code=401, content={"success": False, "message": "No autorizado."})

    cleaned_name = format_title_words(name)
    cleaned_abbr = " ".join((abbreviation or "").split())
    if not cleaned_name or not cleaned_abbr:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Nombre y abreviatura son obligatorios."},
        )

    existing = (
        db.query(MeasurementUnit)
        .filter(func.lower(MeasurementUnit.abbreviation) == cleaned_abbr.lower())
        .first()
    )
    if existing:
        return {
            "success": True,
            "name": existing.name,
            "value": existing.abbreviation,
            "label": existing.abbreviation,
            "created": False,
        }

    db.add(MeasurementUnit(name=cleaned_name, abbreviation=cleaned_abbr))
    db.commit()
    return {
        "success": True,
        "name": cleaned_name,
        "value": cleaned_abbr,
        "label": cleaned_abbr,
        "created": True,
    }


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

    name = format_title_words(name)

    exists = db.query(ProductCategory).filter(ProductCategory.name == name).first()

    if not exists:

        db.add(ProductCategory(name=name))

        db.commit()

    return RedirectResponse("/product-settings", status_code=302)


@router.post("/api/category")
async def api_create_category(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    result = _create_catalog_item_json(request, db, ProductCategory, name)
    if isinstance(result, JSONResponse):
        return result
    return JSONResponse(content=result)


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

    categories = ["Topper", "Base", "Letrero", "Caja", "Decoración", "Cake Topper"]

    materials = ["MDF", "Acrílico", "PVC", "Cartón"]

    colors = ["Dorado", "Plateado", "Negro", "Blanco", "Rojo", "Azul", "Verde"]

    thicknesses = ["1 mm", "2 mm", "3 mm", "5 mm", "9 mm", "12 mm", "18 mm"]

    themes = [
        "Feliz Cumpleaños",
        "Baby Shower",
        "Bautizo",
        "Primera Comunión",
        "San Valentín",
        "Navidad",
        "Año Nuevo",
    ]

    units = [("Milímetros", "mm"), ("Centímetros", "cm"), ("Metros", "m")]

    # CATEGORIAS

    for item in categories:

        exists = db.query(ProductCategory).filter(ProductCategory.name == item).first()

        if not exists:

            db.add(ProductCategory(name=item))

    # MATERIALES

    for item in materials:

        exists = db.query(ProductMaterial).filter(ProductMaterial.name == item).first()

        if not exists:

            db.add(ProductMaterial(name=item))

    # COLORES

    for item in colors:

        exists = db.query(ProductColor).filter(ProductColor.name == item).first()

        if not exists:

            db.add(ProductColor(name=item))

    # ESPESORES

    for item in thicknesses:

        exists = (
            db.query(ProductThickness).filter(ProductThickness.name == item).first()
        )

        if not exists:

            db.add(ProductThickness(name=item))

    # TEMATICAS

    for item in themes:

        exists = db.query(ProductTheme).filter(ProductTheme.name == item).first()

        if not exists:

            db.add(ProductTheme(name=item))

    # UNIDADES

    for name, abbreviation in units:

        exists = (
            db.query(MeasurementUnit)
            .filter(MeasurementUnit.abbreviation == abbreviation)
            .first()
        )

        if not exists:

            db.add(MeasurementUnit(name=name, abbreviation=abbreviation))

    db.commit()

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

    name = format_title_words(name)

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


@router.post("/api/material")
async def api_create_material(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    result = _create_catalog_item_json(request, db, ProductMaterial, name)
    if isinstance(result, JSONResponse):
        return result
    return JSONResponse(content=result)


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

    name = format_title_words(name)

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


@router.post("/api/color")
async def api_create_color(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    result = _create_catalog_item_json(request, db, ProductColor, name)
    if isinstance(result, JSONResponse):
        return result
    return JSONResponse(content=result)


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

    name = format_title_words(name)

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


@router.post("/api/theme")
async def api_create_theme(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    result = _create_catalog_item_json(request, db, ProductTheme, name)
    if isinstance(result, JSONResponse):
        return result
    return JSONResponse(content=result)


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


@router.post("/api/thickness")
async def api_create_thickness(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    result = _create_thickness_json(request, db, name)
    if isinstance(result, JSONResponse):
        return result
    return JSONResponse(content=result)


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


@router.post("/api/unit")
async def api_create_unit(
    request: Request,
    name: str = Form(...),
    abbreviation: str = Form(...),
    db: Session = Depends(get_db),
):
    result = _create_unit_json(request, db, name, abbreviation)
    if isinstance(result, JSONResponse):
        return result
    return JSONResponse(content=result)


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