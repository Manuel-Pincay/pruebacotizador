from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.client import Client
from app.models.design_observation import DesignObservation
from app.models.design_tracking import DesignTracking
from app.models.product import Product
from app.models.production_order import ProductionOrder
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.user import User
from app.services.condensed_service import CONDENSED_QUOTATION_STATUSES
from app.services.production_order_service import (
    DESIGN_PHASE_STATUSES,
    PRODUCTION_STATUS_COLORS,
    PRODUCTION_STATUS_LABELS,
    PRODUCTION_STATUS_SEQUENCE,
    ensure_production_order,
    get_production_order_by_quotation,
    normalize_status,
    transition_status,
)
from app.services.quotation_design_service import get_design_urls

# Mismo flujo lineal que producción (fase diseño + seguimiento posterior)
DESIGN_STATUSES: list[tuple[str, str]] = [
    (code, PRODUCTION_STATUS_LABELS[code]) for code in PRODUCTION_STATUS_SEQUENCE
]

DESIGN_STATUS_LABELS = PRODUCTION_STATUS_LABELS
DESIGN_STATUS_COLORS = PRODUCTION_STATUS_COLORS

DESIGN_PHASE_FILTER = frozenset(DESIGN_PHASE_STATUSES)


def item_is_custom(item: QuotationItem) -> bool:
    if item.product_id is None:
        return True
    product = item.product
    return bool(product and product.custom)


def _product_name(item: QuotationItem) -> str:
    if item.detail:
        return item.detail
    if item.product and item.product.name:
        return item.product.name
    return "—"


def _order_production_status(quotation: Quotation | None) -> str:
    if not quotation:
        return "pendiente"
    order = quotation.production_order
    if order and order.status:
        return normalize_status(order.status)
    return "pendiente"


def _production_order_id(quotation: Quotation | None) -> int | None:
    if quotation and quotation.production_order:
        return quotation.production_order.id
    return None


def _assigned_label_from_po(order: ProductionOrder | None, tracking: DesignTracking | None) -> str:
    if order and order.assignee:
        return order.assignee.full_name or order.assignee.username or "—"
    if order and order.designer:
        return order.designer
    if tracking and tracking.assigned_user and tracking.assigned_user.full_name:
        return tracking.assigned_user.full_name
    if tracking and tracking.assigned_to:
        return tracking.assigned_to
    return "—"


def _assigned_user_id(order: ProductionOrder | None, tracking: DesignTracking | None) -> int | None:
    if order and order.assigned_to_user_id:
        return order.assigned_to_user_id
    if tracking and tracking.assigned_to_user_id:
        return tracking.assigned_to_user_id
    return None


def get_or_create_design_tracking(db: Session, item_id: int) -> DesignTracking:
    tracking = (
        db.query(DesignTracking)
        .filter(DesignTracking.quotation_item_id == item_id)
        .first()
    )
    if tracking:
        return tracking

    tracking = DesignTracking(
        quotation_item_id=item_id,
        status="pendiente_diseno",
    )
    db.add(tracking)
    db.flush()
    return tracking


def _base_custom_items_query(db: Session):
    return (
        db.query(QuotationItem)
        .join(Quotation, QuotationItem.quotation_id == Quotation.id)
        .join(Client, Quotation.client_id == Client.id)
        .outerjoin(Product, QuotationItem.product_id == Product.id)
        .outerjoin(DesignTracking, DesignTracking.quotation_item_id == QuotationItem.id)
        .filter(Quotation.status.in_(CONDENSED_QUOTATION_STATUSES))
        .filter(
            (QuotationItem.product_id.is_(None)) | (Product.custom.is_(True))
        )
        .options(
            joinedload(QuotationItem.quotation).joinedload(Quotation.client),
            joinedload(QuotationItem.quotation).joinedload(Quotation.designs),
            joinedload(QuotationItem.quotation)
            .joinedload(Quotation.production_order)
            .joinedload(ProductionOrder.assignee),
            joinedload(QuotationItem.product),
            joinedload(QuotationItem.design_tracking).joinedload(DesignTracking.assigned_user),
        )
        .order_by(Quotation.delivery_date.asc(), Quotation.id.asc(), QuotationItem.id.asc())
    )


def _matches_design_filter(
    item: QuotationItem,
    *,
    design_filter: str = "",
    assigned_user_id: int | None = None,
    designer_scope_user_id: int | None = None,
) -> bool:
    quotation = item.quotation
    po = quotation.production_order if quotation else None
    tracking = item.design_tracking
    production_status = _order_production_status(quotation)
    assigned_id = _assigned_user_id(po, tracking)

    if designer_scope_user_id is not None:
        if assigned_id and assigned_id != designer_scope_user_id:
            return False

    if design_filter == "mine":
        if not assigned_user_id:
            return False
        if assigned_id != assigned_user_id:
            return False
    elif design_filter == "pending":
        if production_status not in DESIGN_PHASE_FILTER:
            return False
    elif design_filter == "diseno":
        if production_status != "diseno":
            return False
    elif design_filter == "produccion":
        if production_status != "produccion":
            return False
    elif design_filter == "envio":
        if production_status != "envio":
            return False
    elif design_filter == "entregado":
        if production_status != "entregado":
            return False

    return True


def build_design_row(item: QuotationItem) -> dict[str, Any]:
    quotation = item.quotation
    client = quotation.client if quotation else None
    po = quotation.production_order if quotation else None
    tracking = item.design_tracking
    production_status = _order_production_status(quotation)

    return {
        "item_id": item.id,
        "quotation_id": quotation.id if quotation else None,
        "production_order_id": po.id if po else None,
        "client_name": client.name if client else "—",
        "product_name": _product_name(item),
        "quantity": item.quantity or 0,
        "measure": item.measure or "—",
        "theme": item.theme or "—",
        "color": item.color or "—",
        "delivery_date": quotation.delivery_date if quotation else None,
        "design_status": production_status,
        "design_status_label": PRODUCTION_STATUS_LABELS.get(production_status, production_status),
        "assigned_to": _assigned_label_from_po(po, tracking),
        "assigned_to_user_id": _assigned_user_id(po, tracking),
        "design_urls": get_design_urls(quotation) if quotation else [],
        "production_status": production_status,
    }


def list_design_items(
    db: Session,
    *,
    design_filter: str = "",
    assigned_user_id: int | None = None,
    designer_scope_user_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    items = _base_custom_items_query(db).all()
    rows: list[dict[str, Any]] = []

    for item in items:
        if not item_is_custom(item):
            continue
        if not _matches_design_filter(
            item,
            design_filter=design_filter,
            assigned_user_id=assigned_user_id,
            designer_scope_user_id=designer_scope_user_id,
        ):
            continue
        rows.append(build_design_row(item))

    if limit:
        return rows[:limit]
    return rows


def compute_design_kpis(db: Session, designer_scope_user_id: int | None = None) -> dict[str, int]:
    items = _base_custom_items_query(db).all()
    kpis = {code: 0 for code in PRODUCTION_STATUS_SEQUENCE}

    for item in items:
        if not item_is_custom(item):
            continue
        quotation = item.quotation
        po = quotation.production_order if quotation else None
        tracking = item.design_tracking
        production_status = _order_production_status(quotation)

        if designer_scope_user_id is not None:
            assigned_id = _assigned_user_id(po, tracking)
            if assigned_id and assigned_id != designer_scope_user_id:
                continue

        if production_status in kpis:
            kpis[production_status] += 1

    return kpis


def _add_observation(
    db: Session,
    tracking: DesignTracking,
    *,
    user: User | None,
    note: str,
) -> None:
    db.add(
        DesignObservation(
            design_tracking_id=tracking.id,
            user_id=user.id if user else None,
            user_name=user.full_name if user else "Sistema",
            note=note.strip(),
        )
    )


def _ensure_po_for_item(db: Session, item: QuotationItem, user: User | None) -> ProductionOrder:
    quotation = item.quotation
    if not quotation:
        raise ValueError("Cotización no encontrada.")
    order = get_production_order_by_quotation(db, quotation.id)
    if not order:
        order = ensure_production_order(db, quotation, user_id=user.id if user else None)
        db.flush()
    return order


def update_design_status(
    db: Session,
    item_id: int,
    *,
    status: str,
    user: User | None,
    note: str = "",
) -> dict[str, Any]:
    """Acciones de ítem alineadas al flujo lineal de ProductionOrder."""
    item = (
        db.query(QuotationItem)
        .options(
            joinedload(QuotationItem.quotation).joinedload(Quotation.production_order),
            joinedload(QuotationItem.design_tracking),
        )
        .filter(QuotationItem.id == item_id)
        .first()
    )
    if not item or not item_is_custom(item):
        raise ValueError("Producto personalizado no encontrado.")

    action = (status or "").lower()
    if action not in {"start", "diseno"}:
        raise ValueError(
            "Para completar el diseño use Datos de fabricación y Enviar a producción."
        )

    order = _ensure_po_for_item(db, item, user)
    tracking = item.design_tracking or get_or_create_design_tracking(db, item_id)

    if user and user.role == "disenador":
        from app.services.production_order_service import assign_designer as assign_po_designer

        if not order.assigned_to_user_id:
            assign_po_designer(db, order, user.id)
            order = get_production_order_by_quotation(db, item.quotation_id) or order
        tracking.assigned_to_user_id = user.id
        tracking.assigned_to = user.full_name or user.username

    current = normalize_status(order.status)
    if current == "pendiente":
        transition_status(
            db,
            order,
            "diseno",
            user=user,
            notes=note.strip() or "Inicio de diseño desde revisión de ítem.",
        )
    elif note.strip():
        _add_observation(db, tracking, user=user, note=note.strip())
        db.commit()

    tracking.status = "en_diseno"
    tracking.updated_at = datetime.utcnow()
    db.commit()

    po_status = normalize_status(order.status)
    return {
        "status": po_status,
        "status_label": PRODUCTION_STATUS_LABELS.get(po_status, po_status),
        "production_order_id": order.id,
    }


def add_design_observation(
    db: Session,
    item_id: int,
    *,
    user: User | None,
    note: str,
) -> DesignObservation:
    if not note.strip():
        raise ValueError("La observación no puede estar vacía.")

    item = db.query(QuotationItem).filter(QuotationItem.id == item_id).first()
    if not item or not item_is_custom(item):
        raise ValueError("Producto personalizado no encontrado.")

    tracking = item.design_tracking or get_or_create_design_tracking(db, item_id)
    observation = DesignObservation(
        design_tracking_id=tracking.id,
        user_id=user.id if user else None,
        user_name=user.full_name if user else "Sistema",
        note=note.strip(),
    )
    db.add(observation)
    db.commit()
    db.refresh(observation)
    return observation


def assign_designer(
    db: Session,
    item_id: int,
    *,
    designer_user_id: int | None,
    note: str = "",
    actor: User | None = None,
) -> ProductionOrder | None:
    item = (
        db.query(QuotationItem)
        .options(joinedload(QuotationItem.quotation))
        .filter(QuotationItem.id == item_id)
        .first()
    )
    if not item or not item_is_custom(item):
        raise ValueError("Producto personalizado no encontrado.")

    from app.services.production_order_service import assign_designer as assign_po_designer

    order = _ensure_po_for_item(db, item, actor)
    assign_po_designer(db, order, designer_user_id)

    tracking = item.design_tracking or get_or_create_design_tracking(db, item_id)
    designer = None
    if designer_user_id:
        designer = db.query(User).filter(User.id == designer_user_id).first()
        if not designer or designer.role != "disenador":
            raise ValueError("Diseñador no válido.")
        tracking.assigned_to_user_id = designer.id
        tracking.assigned_to = designer.full_name or designer.username
    else:
        tracking.assigned_to_user_id = None
        tracking.assigned_to = None
    tracking.updated_at = datetime.utcnow()

    if designer:
        msg = note.strip() or f"Asignado a {tracking.assigned_to}"
        _add_observation(db, tracking, user=actor, note=msg)

    db.commit()
    return get_production_order_by_quotation(db, item.quotation_id)


def get_design_detail(db: Session, item_id: int) -> dict[str, Any] | None:
    item = (
        db.query(QuotationItem)
        .options(
            joinedload(QuotationItem.quotation).joinedload(Quotation.client),
            joinedload(QuotationItem.quotation).joinedload(Quotation.designs),
            joinedload(QuotationItem.quotation)
            .joinedload(Quotation.production_order)
            .joinedload(ProductionOrder.assignee),
            joinedload(QuotationItem.product),
            joinedload(QuotationItem.design_tracking)
            .joinedload(DesignTracking.observations)
            .joinedload(DesignObservation.user),
            joinedload(QuotationItem.design_tracking).joinedload(DesignTracking.assigned_user),
        )
        .filter(QuotationItem.id == item_id)
        .first()
    )
    if not item or not item_is_custom(item):
        return None

    tracking = item.design_tracking or get_or_create_design_tracking(db, item.id)
    db.commit()

    quotation = item.quotation
    client = quotation.client if quotation else None
    po = quotation.production_order if quotation else None
    production_status = _order_production_status(quotation)

    return {
        "item_id": item.id,
        "quotation_id": quotation.id if quotation else None,
        "production_order_id": po.id if po else None,
        "quotation_date": quotation.created_at if quotation else None,
        "delivery_date": quotation.delivery_date if quotation else None,
        "client_name": client.name if client else "—",
        "client_phone": client.phone if client else "",
        "client_address": client.address if client else "",
        "client_observations": client.observations if client else "",
        "product_name": _product_name(item),
        "quantity": item.quantity or 0,
        "measure": item.measure or "—",
        "theme": item.theme or "—",
        "color": item.color or "—",
        "design_status": production_status,
        "design_status_label": PRODUCTION_STATUS_LABELS.get(production_status, production_status),
        "assigned_to": _assigned_label_from_po(po, tracking),
        "assigned_to_user_id": _assigned_user_id(po, tracking),
        "production_status": production_status,
        "design_urls": get_design_urls(quotation) if quotation else [],
        "observations": [
            {
                "id": obs.id,
                "user_name": obs.user_name or "—",
                "note": obs.note,
                "created_at": obs.created_at.isoformat() if obs.created_at else None,
            }
            for obs in sorted(
                tracking.observations or [],
                key=lambda row: row.created_at or datetime.min,
                reverse=True,
            )
        ],
    }


def list_designers(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == "disenador", User.active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )
