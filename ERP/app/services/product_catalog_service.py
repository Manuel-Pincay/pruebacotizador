from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.productcategory import ProductCategory
from app.models.productcolor import ProductColor
from app.models.productmaterial import ProductMaterial
from app.models.producttheme import ProductTheme
from app.utils.text_format import format_title_words


def _ensure_catalog_value(db: Session, model, name: str) -> str:
    cleaned = format_title_words(name)
    if not cleaned:
        return ""

    existing = (
        db.query(model)
        .filter(func.lower(model.name) == cleaned.lower())
        .first()
    )
    if existing:
        return existing.name

    db.add(model(name=cleaned))
    db.flush()
    return cleaned


def ensure_product_catalog_values(
    db: Session,
    *,
    category: str = "",
    theme: str = "",
    material: str = "",
    color: str = "",
) -> dict[str, str]:
    """Crea entradas de catálogo si no existen y devuelve los valores normalizados."""
    return {
        "category": _ensure_catalog_value(db, ProductCategory, category),
        "theme": _ensure_catalog_value(db, ProductTheme, theme),
        "material": _ensure_catalog_value(db, ProductMaterial, material),
        "color": _ensure_catalog_value(db, ProductColor, color),
    }
