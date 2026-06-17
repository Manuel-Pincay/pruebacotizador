import uuid

from sqlalchemy.orm import Session

from app.models.product import Product
from app.utils.text_format import format_title_words


def create_custom_product_from_quotation(
    db: Session,
    *,
    name: str,
    description: str | None = None,
    material: str | None = None,
    color: str | None = None,
    size: str | None = None,
    thickness: str | None = None,
    theme: str | None = None,
    price: float = 0,
    image: str | None = None,
) -> Product | None:
    """
    Registra un producto personalizado en el catálogo.
    Cada ítem manual de cotización genera su propio registro.
    """
    product_name = format_title_words(name)
    if not product_name:
        return None

    product = Product(
        code=f"AUTO-{uuid.uuid4().hex[:8].upper()}",
        name=product_name,
        description=(description or product_name or ""),
        category="Personalizado",
        material=format_title_words(material) if material else "",
        color=format_title_words(color) if color else "",
        size=size or "",
        thickness=thickness or "",
        theme=format_title_words(theme) if theme else "",
        price=float(price or 0),
        cost=0,
        stock=0,
        custom=True,
        image=image or "",
    )

    db.add(product)
    db.flush()

    return product


def sync_product_image(db: Session, product_id: int | None, image_name: str | None) -> None:
    if not product_id or not image_name:
        return
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.image = image_name


def resolve_custom_product_id(
    db: Session,
    *,
    item_data: dict,
    image: str | None = None,
) -> int | None:
    """Resuelve product_id para un ítem personalizado de cotización."""
    raw_product_id = item_data.get("product_id")
    if raw_product_id not in (None, "", 0, "0"):
        try:
            return int(raw_product_id)
        except (TypeError, ValueError):
            return None

    item_type = (item_data.get("type") or "").lower()
    if item_type != "custom":
        return None

    product = create_custom_product_from_quotation(
        db,
        name=item_data.get("detail", ""),
        description=item_data.get("detail", ""),
        color=item_data.get("color"),
        size=item_data.get("measure"),
        theme=item_data.get("theme"),
        price=item_data.get("price", 0),
        image=image,
    )

    return product.id if product else None
