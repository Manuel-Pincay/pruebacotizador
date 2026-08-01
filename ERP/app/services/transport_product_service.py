"""Producto de catálogo para costo de envío en cotizaciones."""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.services.quotation_service import compute_item_total, recalculate_quotation

TRANSPORT_PRODUCT_NAME = "Servicio de transporte"
TRANSPORT_PRODUCT_CODE = "SRV-TRANSPORTE"


def get_or_create_transport_service_product(db: Session) -> Product:
    product = (
        db.query(Product)
        .filter(
            or_(
                Product.code == TRANSPORT_PRODUCT_CODE,
                Product.name.ilike(TRANSPORT_PRODUCT_NAME),
            )
        )
        .first()
    )
    if product:
        if product.tarifa_iva not in (0, 0.0) or str(product.codigo_iva or "") not in ("0", ""):
            product.tarifa_iva = 0
            product.codigo_iva = "0"
            db.flush()
        return product

    product = Product(
        code=TRANSPORT_PRODUCT_CODE,
        name=TRANSPORT_PRODUCT_NAME,
        description=TRANSPORT_PRODUCT_NAME,
        category="Servicios",
        price=0,
        cost=0,
        stock=0,
        custom=False,
        codigo_iva="0",
        tarifa_iva=0,
    )
    db.add(product)
    db.flush()
    return product


def is_transport_product_id(product_id, transport_id: int) -> bool:
    if product_id is None or transport_id is None:
        return False
    try:
        return int(product_id) == int(transport_id)
    except (TypeError, ValueError):
        return False


def is_transport_item_data(item: dict, transport_id: int) -> bool:
    if item.get("is_transport"):
        return True
    detail = (item.get("detail") or "").strip().lower()
    if detail == TRANSPORT_PRODUCT_NAME.lower():
        return True
    return is_transport_product_id(item.get("product_id"), transport_id)


def merge_shipping_into_items(db: Session, items_data: list, shipping_cost) -> list:
    """Convierte shipping_cost en línea de producto Servicio de transporte (IVA 0%)."""
    transport = get_or_create_transport_service_product(db)
    transport_id = transport.id
    shipping = float(shipping_cost or 0)

    merged = [item for item in items_data if not is_transport_item_data(item, transport_id)]

    if shipping > 0:
        merged.append(
            {
                "type": "inventory",
                "product_id": transport_id,
                "quantity": 1,
                "detail": TRANSPORT_PRODUCT_NAME,
                "measure": "",
                "theme": "",
                "color": "",
                "logo_type": "sin_logo",
                "item_discount": 0,
                "price": shipping,
                "total": shipping,
                "is_transport": True,
            }
        )
    return merged


def quotation_shipping_amount(quotation: Quotation, transport_id: int | None = None) -> float:
    if transport_id:
        for item in quotation.items or []:
            if is_transport_product_id(item.product_id, transport_id):
                return float(item.unit_price or item.total or 0)
    legacy = float(getattr(quotation, "shipping_cost", None) or 0)
    return legacy


def sync_quotation_shipping_item(db: Session, quotation: Quotation, shipping_cost: float) -> None:
    """Actualiza la línea de transporte en una cotización existente."""
    transport = get_or_create_transport_service_product(db)
    transport_id = transport.id
    shipping = float(shipping_cost or 0)

    existing = (
        db.query(QuotationItem)
        .filter(
            QuotationItem.quotation_id == quotation.id,
            QuotationItem.product_id == transport_id,
        )
        .first()
    )

    if shipping <= 0:
        if existing:
            db.delete(existing)
        quotation.shipping_cost = 0
        recalculate_quotation(quotation, db)
        return

    line_total = compute_item_total(1, shipping, 0)
    if existing:
        existing.quantity = 1
        existing.unit_price = shipping
        existing.total = line_total
        existing.detail = TRANSPORT_PRODUCT_NAME
        existing.item_discount = 0
    else:
        db.add(
            QuotationItem(
                quotation_id=quotation.id,
                product_id=transport_id,
                quantity=1,
                detail=TRANSPORT_PRODUCT_NAME,
                measure="",
                theme="",
                color="",
                logo=False,
                logo_type="sin_logo",
                item_discount=0,
                unit_price=shipping,
                total=line_total,
            )
        )

    quotation.shipping_cost = 0
    recalculate_quotation(quotation, db)
