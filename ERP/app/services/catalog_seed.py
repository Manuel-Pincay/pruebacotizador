"""Datos iniciales de catálogos de producto (categorías, materiales, etc.)."""

from sqlalchemy.orm import Session

from app.models.measurementunit import MeasurementUnit
from app.models.productcategory import ProductCategory
from app.models.productcolor import ProductColor
from app.models.productmaterial import ProductMaterial
from app.models.producttheme import ProductTheme
from app.models.productthickness import ProductThickness

DEFAULT_CATEGORIES = [
    "Topper",
    "Base",
    "Letrero",
    "Caja",
    "Decoración",
    "Cake Topper",
]

DEFAULT_MATERIALS = ["MDF", "Acrílico", "PVC", "Cartón"]

DEFAULT_COLORS = [
    "Dorado",
    "Plateado",
    "Negro",
    "Blanco",
    "Rojo",
    "Azul",
    "Verde",
]

DEFAULT_THICKNESSES = [
    "1 mm",
    "2 mm",
    "3 mm",
    "5 mm",
    "9 mm",
    "12 mm",
    "18 mm",
]

DEFAULT_THEMES = [
    "Feliz Cumpleaños",
    "Baby Shower",
    "Bautizo",
    "Primera Comunión",
    "San Valentín",
    "Navidad",
    "Año Nuevo",
]

DEFAULT_UNITS = [
    ("Milímetros", "mm"),
    ("Centímetros", "cm"),
    ("Metros", "m"),
]


def seed_product_catalogs(db: Session) -> dict[str, int]:
    """Inserta catálogos base si no existen. Devuelve cuántos registros se crearon."""
    created = {
        "categories": 0,
        "materials": 0,
        "colors": 0,
        "thicknesses": 0,
        "themes": 0,
        "units": 0,
    }

    for name in DEFAULT_CATEGORIES:
        if not db.query(ProductCategory).filter(ProductCategory.name == name).first():
            db.add(ProductCategory(name=name))
            created["categories"] += 1

    for name in DEFAULT_MATERIALS:
        if not db.query(ProductMaterial).filter(ProductMaterial.name == name).first():
            db.add(ProductMaterial(name=name))
            created["materials"] += 1

    for name in DEFAULT_COLORS:
        if not db.query(ProductColor).filter(ProductColor.name == name).first():
            db.add(ProductColor(name=name))
            created["colors"] += 1

    for name in DEFAULT_THICKNESSES:
        if not db.query(ProductThickness).filter(ProductThickness.name == name).first():
            db.add(ProductThickness(name=name))
            created["thicknesses"] += 1

    for name in DEFAULT_THEMES:
        if not db.query(ProductTheme).filter(ProductTheme.name == name).first():
            db.add(ProductTheme(name=name))
            created["themes"] += 1

    for name, abbreviation in DEFAULT_UNITS:
        exists = (
            db.query(MeasurementUnit)
            .filter(MeasurementUnit.abbreviation == abbreviation)
            .first()
        )
        if not exists:
            db.add(MeasurementUnit(name=name, abbreviation=abbreviation))
            created["units"] += 1

    if any(created.values()):
        db.commit()

    return created
