"""Servicio CMS del home / carrusel de la tienda."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.store_home_settings import StoreHomeSettings
from app.models.store_slide import StoreSlide
from app.services.store_catalog import store_products_query

DEFAULT_ACCENT = "#E8A0AC"


def get_or_create_home_settings(db: Session) -> StoreHomeSettings:
    row = db.query(StoreHomeSettings).filter(StoreHomeSettings.id == 1).first()
    if row:
        changed = False
        if not (row.contact_phone or "").strip():
            row.contact_phone = "0983546624"
            changed = True
        if not (row.contact_whatsapp or "").strip():
            row.contact_whatsapp = "593983546624"
            changed = True
        if changed:
            db.commit()
            db.refresh(row)
        return row
    row = StoreHomeSettings(
        id=1,
        show_top_bar=True,
        top_bar_left="Envíos a todo el país",
        top_bar_right="Productos personalizados con tu logo",
        accent_color=DEFAULT_ACCENT,
        feature_1_title="Calidad",
        feature_1_text="Materiales seleccionados para resultados profesionales",
        feature_2_title="Envíos rápidos",
        feature_2_text="Despachamos tu pedido con cuidado y puntualidad",
        feature_3_title="Personalizados",
        feature_3_text="Diseños a medida con tu marca o temática",
        show_categories=True,
        featured_categories="",
        show_featured_products=True,
        featured_product_ids="",
        show_trust_bar=True,
        trust_1_title="Compra segura",
        trust_1_text="Pago por transferencia verificado",
        trust_2_title="Atención personalizada",
        trust_2_text="Te ayudamos por WhatsApp",
        trust_3_title="Empaque seguro",
        trust_3_text="Protegemos cada detalle",
        trust_4_title="Clientes felices",
        trust_4_text="Pedidos cotizados y acompañados",
        show_newsletter=True,
        newsletter_title="Suscríbete a nuestro newsletter",
        footer_blurb="Insumos y detalles para dar vida a tus creaciones.",
        contact_phone="0983546624",
        contact_whatsapp="593983546624",
        contact_hours="Lun–Vie 9:00–18:00",
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_active_slides(db: Session) -> list[StoreSlide]:
    return (
        db.query(StoreSlide)
        .filter(StoreSlide.active.is_(True))
        .order_by(StoreSlide.sort_order.asc(), StoreSlide.id.asc())
        .all()
    )


def list_all_slides(db: Session) -> list[StoreSlide]:
    return (
        db.query(StoreSlide)
        .order_by(StoreSlide.sort_order.asc(), StoreSlide.id.asc())
        .all()
    )


def _split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]


def parse_nav_links(raw: str | None) -> list[dict]:
    """Líneas 'Etiqueta|/ruta' o solo categoría → /tienda?category=..."""
    links = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            label, url = line.split("|", 1)
            links.append({"label": label.strip(), "url": url.strip() or "/tienda"})
        else:
            links.append(
                {
                    "label": line,
                    "url": f"/tienda?category={line}",
                }
            )
    return links


def featured_category_cards(db: Session, settings: StoreHomeSettings) -> list[dict]:
    names = _split_csv(settings.featured_categories)
    if not names:
        # Fallback: primeras categorías con productos en tienda
        rows = (
            store_products_query(db)
            .with_entities(Product.category)
            .filter(Product.category.isnot(None), Product.category != "")
            .distinct()
            .order_by(Product.category.asc())
            .limit(4)
            .all()
        )
        names = [r[0] for r in rows if r[0]]

    cards = []
    for name in names[:8]:
        sample = (
            store_products_query(db)
            .filter(Product.category == name)
            .order_by(Product.id.desc())
            .first()
        )
        cards.append(
            {
                "name": name,
                "description": f"Explora {name.lower()}",
                "image": sample.image if sample else None,
                "url": f"/tienda?category={name}",
            }
        )
    return cards


def featured_products(db: Session, settings: StoreHomeSettings, limit: int = 8) -> list[Product]:
    ids = []
    for part in _split_csv(settings.featured_product_ids):
        try:
            ids.append(int(part))
        except ValueError:
            continue
    products: list[Product] = []
    if ids:
        by_id = {
            p.id: p
            for p in store_products_query(db).filter(Product.id.in_(ids)).all()
        }
        for pid in ids:
            if pid in by_id:
                products.append(by_id[pid])
    if len(products) < limit:
        exclude = {p.id for p in products}
        query = store_products_query(db)
        if exclude:
            query = query.filter(~Product.id.in_(list(exclude)))
        extra = query.order_by(Product.name.asc()).limit(limit - len(products)).all()
        products.extend(extra)
    return products[:limit]


def store_theme_color(settings: StoreHomeSettings | None, company_primary: str | None) -> str:
    if settings and (settings.accent_color or "").strip():
        return settings.accent_color.strip()
    # Rosa del mockup si no hay color de empresa usable
    if company_primary and company_primary.lower() not in {"#7c3aed", "#7c3aed"}:
        return company_primary
    return DEFAULT_ACCENT
