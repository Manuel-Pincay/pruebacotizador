import uuid

from sqlalchemy.orm import Session

from app.models.product import Product


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
) -> Product | None:
    """
    Crea un producto personalizado en el catálogo o retorna uno existente
    con el mismo nombre. Solo debe usarse para ítems manuales de cotización.
    """
    product_name = (name or "").strip()
    if not product_name:
        return None

    existing_product = (
        db.query(Product)
        .filter(Product.name == product_name)
        .first()
    )
    if existing_product:
        return existing_product

    product = Product(
        code=f"AUTO-{uuid.uuid4().hex[:8].upper()}",
        name=product_name,
        description=(description or product_name or ""),
        category="Personalizado",
        material=material or "",
        color=color or "",
        size=size or "",
        thickness=thickness or "",
        theme=theme or "",
        price=float(price or 0),
        cost=0,
        stock=0,
        custom=True,
        image="",
    )

    db.add(product)
    db.flush()

    return product


def resolve_custom_product_id(
    db: Session,
    *,
    item_data: dict,
) -> int | None:
    """Resuelve product_id para un ítem personalizado de cotización."""
    raw_product_id = item_data.get("product_id")
    if raw_product_id not in (None, "", 0, "0"):
        try:
            return int(raw_product_id)
        except (TypeError, ValueError):
            return None

    product = create_custom_product_from_quotation(
        db,
        name=item_data.get("detail", ""),
        description=item_data.get("detail", ""),
        color=item_data.get("color"),
        size=item_data.get("measure"),
        theme=item_data.get("theme"),
        price=item_data.get("price", 0),
    )

    return product.id if product else None
