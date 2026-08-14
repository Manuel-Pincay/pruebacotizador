"""Consultas y checkout de la tienda pública."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.models.product import Product
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.services.quotation_service import compute_item_total, recalculate_quotation
from app.services.store_order_service import new_store_access_token
from app.utils.text_format import format_title_words


def store_products_query(db: Session):
    return db.query(Product).filter(
        Product.active.is_(True),
        Product.store_visible.is_(True),
    )


def get_store_product(db: Session, product_id: int) -> Product | None:
    return (
        store_products_query(db)
        .filter(Product.id == product_id)
        .first()
    )


def list_store_products(
    db: Session,
    *,
    q: str = "",
    category: str = "",
    limit: int = 60,
    offset: int = 0,
) -> tuple[list[Product], int]:
    query = store_products_query(db)
    search = (q or "").strip()
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Product.name.ilike(term),
                Product.code.ilike(term),
                Product.description.ilike(term),
                Product.category.ilike(term),
            )
        )
    cat = (category or "").strip()
    if cat:
        query = query.filter(Product.category == cat)

    total = query.count()
    products = (
        query.order_by(Product.name.asc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return products, total


def store_category_options(db: Session) -> list[str]:
    rows = (
        store_products_query(db)
        .with_entities(Product.category)
        .filter(Product.category.isnot(None), Product.category != "")
        .distinct()
        .order_by(Product.category.asc())
        .all()
    )
    return [r[0] for r in rows if r[0]]


def resolve_cart_lines(db: Session, cart_items: list[dict]) -> list[dict]:
    """Une carrito con productos válidos de tienda; descarta IDs inválidos."""
    lines: list[dict] = []
    for row in cart_items:
        product = get_store_product(db, int(row["product_id"]))
        if not product:
            continue
        qty = int(row["quantity"])
        unit = float(product.price or 0)
        lines.append(
            {
                "product": product,
                "product_id": product.id,
                "quantity": qty,
                "unit_price": unit,
                "line_total": compute_item_total(qty, unit, 0),
            }
        )
    return lines


def cart_subtotal(lines: list[dict]) -> float:
    return sum(float(line["line_total"]) for line in lines)


def find_or_create_store_client(
    db: Session,
    *,
    name: str,
    phone: str,
    email: str,
    ruc_ci: str = "",
    address: str = "",
) -> Client:
    name = format_title_words((name or "").strip())
    phone = (phone or "").strip()
    email = (email or "").strip().lower()
    ruc_ci = (ruc_ci or "").strip()
    address = format_title_words((address or "").strip())

    client = None
    if ruc_ci:
        client = db.query(Client).filter(Client.ruc_ci == ruc_ci).first()
    if not client and email:
        client = db.query(Client).filter(Client.email == email).first()

    if client:
        if not client.phone and phone:
            client.phone = phone
        if not client.email and email:
            client.email = email
        if not client.address and address:
            client.address = address
        if not client.name and name:
            client.name = name
        return client

    client = Client(
        name=name or "Cliente tienda",
        phone=phone or None,
        email=email or None,
        ruc_ci=ruc_ci or None,
        address=address or None,
        client_type="tienda",
        tipo_identificacion="CEDULA" if ruc_ci and len(ruc_ci) <= 10 else "RUC",
        observations="Alta automática desde tienda virtual",
    )
    db.add(client)
    db.flush()
    return client


def create_store_quotation(
    db: Session,
    *,
    client: Client,
    lines: list[dict],
) -> Quotation:
    if not lines:
        raise ValueError("El carrito está vacío.")

    config = db.query(CompanyConfig).first()
    iva = float(getattr(config, "iva_default", 0) or 0)

    quotation = Quotation(
        client_id=client.id,
        subtotal=0,
        discount=0,
        iva=iva,
        total=0,
        shipping_cost=0,
        status="pendiente",
        source="store",
        store_access_token=new_store_access_token(),
        created_by_client_id=client.id,
        design_file=None,
    )
    db.add(quotation)
    db.flush()

    for line in lines:
        product = line["product"]
        qty = int(line["quantity"])
        unit = float(line["unit_price"])
        db.add(
            QuotationItem(
                quotation_id=quotation.id,
                product_id=product.id,
                quantity=qty,
                detail=product.name or "",
                measure=product.size or "",
                theme=product.theme or "",
                color=product.color or "",
                logo=False,
                logo_type="sin_logo",
                item_discount=0,
                unit_price=unit,
                total=compute_item_total(qty, unit, 0),
                product_image=product.image,
            )
        )

    db.flush()
    db.expire(quotation, ["items"])
    recalculate_quotation(quotation, db)
    return quotation
