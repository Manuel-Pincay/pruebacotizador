import uuid

from sqlalchemy.orm import Session

from app.models.product import Product
from app.utils.sri_constants import codigo_iva_from_tarifa
from app.utils.text_format import format_title_words


def create_billable_product(
    db: Session,
    *,
    name: str,
    description: str | None = None,
    price: float = 0,
    tarifa_iva: float = 0,
    codigo_iva: str | None = None,
    custom: bool = True,
    category: str = "Personalizado",
    material: str | None = None,
    color: str | None = None,
    size: str | None = None,
    thickness: str | None = None,
    theme: str | None = None,
    image: str | None = None,
    code: str | None = None,
) -> Product | None:
    """Crea un producto en catálogo con datos mínimos para facturación SRI."""
    product_name = format_title_words(name)
    if not product_name:
        return None

    tarifa = float(tarifa_iva or 0)
    codigo = codigo_iva_from_tarifa(tarifa, codigo_iva)
    desc = (description or product_name or "")[:500]

    product = Product(
        code=code or f"AUTO-{uuid.uuid4().hex[:8].upper()}",
        name=product_name,
        description=desc,
        category=category,
        material=format_title_words(material) if material else "",
        color=format_title_words(color) if color else "",
        size=size or "",
        thickness=thickness or "",
        theme=format_title_words(theme) if theme else "",
        price=float(price or 0),
        cost=0,
        stock=0,
        custom=custom,
        active=True,
        image=image or "",
        tarifa_iva=tarifa,
        codigo_iva=codigo,
    )

    db.add(product)
    db.flush()
    return product


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
    tarifa_iva: float = 0,
    codigo_iva: str | None = None,
) -> Product | None:
    """Registra un producto personalizado de cotización con IVA para facturación."""
    return create_billable_product(
        db,
        name=name,
        description=description or name,
        material=material,
        color=color,
        size=size,
        thickness=thickness,
        theme=theme,
        price=price,
        image=image,
        tarifa_iva=tarifa_iva,
        codigo_iva=codigo_iva,
        custom=True,
        category="Personalizado",
    )


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
    default_tarifa_iva: float = 0,
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

    tarifa = item_data.get("tarifa_iva")
    if tarifa is None or tarifa == "":
        tarifa = default_tarifa_iva
    try:
        tarifa = float(tarifa)
    except (TypeError, ValueError):
        tarifa = float(default_tarifa_iva or 0)

    product = create_custom_product_from_quotation(
        db,
        name=item_data.get("detail", ""),
        description=item_data.get("detail", ""),
        color=item_data.get("color"),
        size=item_data.get("measure"),
        theme=item_data.get("theme"),
        price=item_data.get("price", 0),
        image=image,
        tarifa_iva=tarifa,
        codigo_iva=item_data.get("codigo_iva"),
    )

    return product.id if product else None


def ensure_billing_line_product(
    db: Session,
    item: dict,
    *,
    default_tarifa_iva: float = 0,
) -> dict:
    """Si la línea es manual o sin producto, crea el producto en BD con IVA SRI."""
    product_id = item.get("product_id")
    if product_id:
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            product_id = None

    if product_id:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            if product.tarifa_iva is None or product.codigo_iva in (None, ""):
                tarifa = float(item.get("tarifa_iva") if item.get("tarifa_iva") is not None else default_tarifa_iva)
                product.tarifa_iva = tarifa
                product.codigo_iva = codigo_iva_from_tarifa(tarifa, item.get("codigo_iva"))
                if not (product.description or "").strip():
                    product.description = (item.get("descripcion") or product.name or "")[:500]
                db.flush()
            item.setdefault("codigo_principal", product.code)
            item.setdefault("descripcion", product.description or product.name)
            item.setdefault("tarifa_iva", product.tarifa_iva)
            item.setdefault("codigo_iva", product.codigo_iva)
        return item

    descripcion = (item.get("descripcion") or "").strip()
    if not descripcion:
        return item

    tarifa = item.get("tarifa_iva")
    if tarifa is None or tarifa == "":
        tarifa = default_tarifa_iva
    try:
        tarifa = float(tarifa)
    except (TypeError, ValueError):
        tarifa = float(default_tarifa_iva or 0)

    product = create_billable_product(
        db,
        name=descripcion,
        description=descripcion,
        price=item.get("precio_unitario", 0),
        tarifa_iva=tarifa,
        codigo_iva=item.get("codigo_iva"),
        custom=True,
        category="Facturación",
    )
    if not product:
        return item

    item["product_id"] = product.id
    item["codigo_principal"] = product.code
    item["descripcion"] = product.description or product.name
    item["tarifa_iva"] = product.tarifa_iva
    item["codigo_iva"] = product.codigo_iva
    return item


def product_to_billing_payload(product: Product) -> dict:
    return {
        "id": product.id,
        "codigo_principal": (product.code or f"P{product.id}")[:50],
        "codigo_auxiliar": product.codigo_auxiliar,
        "descripcion": (product.description or product.name or "Producto")[:500],
        "precio_unitario": float(product.price or 0),
        "tarifa_iva": float(product.tarifa_iva if product.tarifa_iva is not None else 0),
        "codigo_iva": product.codigo_iva or codigo_iva_from_tarifa(product.tarifa_iva or 0),
    }
