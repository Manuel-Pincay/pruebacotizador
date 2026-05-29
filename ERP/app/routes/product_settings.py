from fastapi import APIRouter
from fastapi import Request
from fastapi import Depends
from fastapi import Form

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.productcategory import ProductCategory
from app.models.productmaterial import ProductMaterial
from app.models.productcolor import ProductColor
from app.models.producttheme import ProductTheme
from app.models.productthickness import ProductThickness
from app.models.measurementunit import MeasurementUnit

router = APIRouter(prefix="/product-settings", tags=["product_settings"])

templates = Jinja2Templates(directory="app/templates")

from app.utils.context import get_global_config

templates.env.globals["inject_global_config"] = get_global_config


@router.get("/", response_class=HTMLResponse)
async def product_settings_page(request: Request, db: Session = Depends(get_db)):

    categories = db.query(ProductCategory).all()

    materials = db.query(ProductMaterial).all()

    colors = db.query(ProductColor).all()

    themes = db.query(ProductTheme).all()

    thicknesses = db.query(ProductThickness).all()

    units = db.query(MeasurementUnit).all()

    return templates.TemplateResponse(
        request=request,
        name="product_settings.html",
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
# CREATE CATEGORY
# =====================================


@router.post("/category/new")
async def create_category(name: str = Form(...), db: Session = Depends(get_db)):

    exists = db.query(ProductCategory).filter(ProductCategory.name == name).first()

    if not exists:

        db.add(ProductCategory(name=name))

        db.commit()

    return RedirectResponse("/product-settings", status_code=302)


# =====================================
# DELETE CATEGORY
# =====================================


@router.get("/category/{category_id}/delete")
async def delete_category(category_id: int, db: Session = Depends(get_db)):

    category = (
        db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    )

    if category:

        db.delete(category)

        db.commit()

    return RedirectResponse("/product-settings", status_code=302)


@router.get("/init")
async def initialize_catalogs(db: Session = Depends(get_db)):

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
    name: str = Form(...),
    db: Session = Depends(get_db)
):

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
    material_id: int,
    db: Session = Depends(get_db)
):

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
    name: str = Form(...),
    db: Session = Depends(get_db)
):

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
    color_id: int,
    db: Session = Depends(get_db)
):

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
    name: str = Form(...),
    db: Session = Depends(get_db)
):

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
    theme_id: int,
    db: Session = Depends(get_db)
):

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
    name: str = Form(...),
    db: Session = Depends(get_db)
):

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
    thickness_id: int,
    db: Session = Depends(get_db)
):

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
    name: str = Form(...),
    abbreviation: str = Form(...),
    db: Session = Depends(get_db)
):

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
    unit_id: int,
    db: Session = Depends(get_db)
):

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