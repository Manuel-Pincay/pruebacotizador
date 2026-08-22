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
from app.services.production_order_service import (
    DESIGN_PHASE_STATUSES,
    PRODUCTION_STATUS_COLORS,
    PRODUCTION_STATUS_LABELS,
    PRODUCTION_STATUS_SEQUENCE,
    ensure_production_order,
    get_production_order_by_quotation,
    normalize_status,
    transition_status,
    work_items_payload,
)
from app.services.quotation_design_service import (
    MAX_QUOTATION_DESIGNS,
    get_design_urls,
    sync_legacy_design_file,
)
from app.services.transport_product_service import TRANSPORT_PRODUCT_CODE, TRANSPORT_PRODUCT_NAME
from app.utils.image_storage import design_image_url

# Cotizaciones visibles en diseño (incluye seguimiento post-producción)
DESIGN_QUOTATION_STATUSES = frozenset({
    "aprobada",
    "produccion",
    "en_produccion",
    "enviada",
    "enviado",
    "entregada",
    "entregado",
})

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


def item_is_transport(item: QuotationItem) -> bool:
    """Costo de envío: no entra al flujo de diseño."""
    product = item.product
    if product:
        code = (product.code or "").strip().upper()
        name = (product.name or "").strip().lower()
        if code == TRANSPORT_PRODUCT_CODE.upper():
            return True
        if name == TRANSPORT_PRODUCT_NAME.lower():
            return True
    detail = (item.detail or "").strip().lower()
    return detail == TRANSPORT_PRODUCT_NAME.lower()


def item_needs_design(item: QuotationItem) -> bool:
    """Ítems que el módulo de diseño debe listar y trabajar (catálogo o personalizados)."""
    return not item_is_transport(item)


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


def _base_design_items_query(db: Session):
    """Ítems de cotizaciones en flujo operativo, excluyendo servicio de transporte."""
    return (
        db.query(QuotationItem)
        .join(Quotation, QuotationItem.quotation_id == Quotation.id)
        .join(Client, Quotation.client_id == Client.id)
        .outerjoin(Product, QuotationItem.product_id == Product.id)
        .outerjoin(DesignTracking, DesignTracking.quotation_item_id == QuotationItem.id)
        .filter(Quotation.status.in_(list(DESIGN_QUOTATION_STATUSES)))
        .filter(
            (Product.id.is_(None))
            | (
                (Product.code.is_(None) | (Product.code != TRANSPORT_PRODUCT_CODE))
                & (Product.name.is_(None) | (Product.name != TRANSPORT_PRODUCT_NAME))
            )
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


# Alias por compatibilidad
_base_custom_items_query = _base_design_items_query


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
    elif design_filter in {"available", "disponibles", "unassigned"}:
        # Cotizaciones/ítems aprobados sin diseñador, listos para tomar
        if production_status not in DESIGN_PHASE_FILTER:
            return False
        if assigned_id is not None:
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
        "can_claim": _assigned_user_id(po, tracking) is None
        and production_status in DESIGN_PHASE_FILTER,
        "design_urls": get_design_urls(quotation) if quotation else [],
        "production_status": production_status,
        "fulfill_from_inventory": bool(getattr(item, "fulfill_from_inventory", False)),
        "design_item_done": bool(getattr(item, "design_item_done", False)),
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
        if not item_needs_design(item):
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


def list_design_order_groups(
    db: Session,
    *,
    design_filter: str = "",
    assigned_user_id: int | None = None,
    designer_scope_user_id: int | None = None,
    limit: int | None = None,
    sort_by: str = "delivery",
) -> list[dict[str, Any]]:
    """Una fila por cotización, con la lista de productos."""
    item_rows = list_design_items(
        db,
        design_filter=design_filter,
        assigned_user_id=assigned_user_id,
        designer_scope_user_id=designer_scope_user_id,
    )
    groups: list[dict[str, Any]] = []
    by_quotation: dict[int, dict[str, Any]] = {}
    for row in item_rows:
        qid = row.get("quotation_id")
        if qid is None:
            continue
        group = by_quotation.get(qid)
        if group is None:
            group = {
                **row,
                "products": [],
                "product_count": 0,
                "total_qty": 0,
                "has_inventory": False,
                "has_production": False,
            }
            by_quotation[qid] = group
            groups.append(group)
        group["products"].append(
            {
                "item_id": row["item_id"],
                "product_name": row["product_name"],
                "quantity": row["quantity"],
                "fulfill_from_inventory": row.get("fulfill_from_inventory", False),
                "design_item_done": row.get("design_item_done", False),
            }
        )
        group["product_count"] = len(group["products"])
        group["total_qty"] += int(row["quantity"] or 0)
        if row.get("fulfill_from_inventory"):
            group["has_inventory"] = True
        else:
            group["has_production"] = True

    groups = sort_design_order_groups(groups, sort_by)
    if limit:
        return groups[:limit]
    return groups


def sort_design_order_groups(groups: list[dict[str, Any]], sort_by: str = "delivery") -> list[dict[str, Any]]:
    """Ordena filas de diseño: delivery, quotation, client, status (+ _desc)."""
    from datetime import date as date_cls

    key = (sort_by or "delivery").strip().lower()
    reverse = key.endswith("_desc")
    if reverse:
        key = key[: -len("_desc")]
    elif key.endswith("_asc"):
        key = key[: -len("_asc")]

    far = date_cls.max

    def sort_key(row: dict[str, Any]):
        if key in {"quotation", "numero", "number", "cotizacion"}:
            return (row.get("quotation_id") is None, row.get("quotation_id") or 0)
        if key in {"client", "cliente"}:
            return ((row.get("client_name") or "").strip().lower(), row.get("quotation_id") or 0)
        if key in {"status", "estado"}:
            return (
                (row.get("design_status") or "").strip().lower(),
                row.get("delivery_date") or far,
                row.get("quotation_id") or 0,
            )
        if key in {"designer", "disenador"}:
            assigned = (row.get("assigned_to") or "").strip().lower()
            unassigned = 0 if row.get("assigned_to_user_id") else 1
            return (unassigned, assigned, row.get("quotation_id") or 0)
        # delivery (default)
        return (row.get("delivery_date") is None, row.get("delivery_date") or far, row.get("quotation_id") or 0)

    return sorted(groups, key=sort_key, reverse=reverse)


def compute_design_kpis(db: Session, designer_scope_user_id: int | None = None) -> dict[str, int]:
    items = _base_design_items_query(db).all()
    seen: dict[str, set[int]] = {code: set() for code in PRODUCTION_STATUS_SEQUENCE}
    available_quotes: set[int] = set()

    for item in items:
        if not item_needs_design(item):
            continue
        quotation = item.quotation
        if not quotation:
            continue
        po = quotation.production_order if quotation else None
        tracking = item.design_tracking
        production_status = _order_production_status(quotation)

        assigned_id = _assigned_user_id(po, tracking)
        if designer_scope_user_id is not None:
            if assigned_id and assigned_id != designer_scope_user_id:
                continue

        if production_status in seen:
            seen[production_status].add(quotation.id)
        if production_status in DESIGN_PHASE_FILTER and assigned_id is None:
            available_quotes.add(quotation.id)

    kpis = {code: len(ids) for code, ids in seen.items()}
    kpis["available"] = len(available_quotes)
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
    if not item or not item_needs_design(item):
        raise ValueError("Producto no encontrado para diseño.")

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
    if not item or not item_needs_design(item):
        raise ValueError("Producto no encontrado para diseño.")

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


def claim_design_item(
    db: Session,
    item_id: int,
    *,
    user: User,
) -> ProductionOrder:
    """Diseñador se autoasigna un ítem/cotización sin diseñador."""
    if not user or user.role != "disenador":
        raise ValueError("Solo un diseñador puede tomarse esta cotización.")

    item = (
        db.query(QuotationItem)
        .options(
            joinedload(QuotationItem.quotation).joinedload(Quotation.production_order),
            joinedload(QuotationItem.design_tracking),
        )
        .filter(QuotationItem.id == item_id)
        .first()
    )
    if not item or not item_needs_design(item):
        raise ValueError("Producto no encontrado para diseño.")

    order = _ensure_po_for_item(db, item, user)
    if order.assigned_to_user_id and order.assigned_to_user_id != user.id:
        raise ValueError("Esta cotización ya fue tomada por otro diseñador.")

    from app.services.production_order_service import assign_designer as assign_po_designer

    if not order.assigned_to_user_id:
        assign_po_designer(db, order, user.id)

    tracking = item.design_tracking or get_or_create_design_tracking(db, item_id)
    tracking.assigned_to_user_id = user.id
    tracking.assigned_to = user.full_name or user.username
    tracking.updated_at = datetime.utcnow()
    _add_observation(
        db,
        tracking,
        user=user,
        note=f"Diseñador se autoasignó: {tracking.assigned_to}",
    )
    db.commit()
    return get_production_order_by_quotation(db, item.quotation_id) or order


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
    if not item or not item_needs_design(item):
        raise ValueError("Producto no encontrado para diseño.")

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
            .joinedload(Quotation.items)
            .joinedload(QuotationItem.product),
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
    if not item or not item_needs_design(item):
        return None

    tracking = item.design_tracking or get_or_create_design_tracking(db, item.id)
    quotation = item.quotation
    if quotation:
        sync_legacy_design_file(db, quotation)
    db.commit()

    client = quotation.client if quotation else None
    po = quotation.production_order if quotation else None
    production_status = _order_production_status(quotation)
    designs = []
    if quotation:
        for design in sorted(quotation.designs or [], key=lambda d: d.sort_order or 0):
            url = design_image_url(design.filename)
            if not url:
                continue
            designs.append({
                "id": design.id,
                "filename": design.filename,
                "url": url,
            })

    products = work_items_payload(quotation)
    products_done = sum(1 for row in products if row.get("design_item_done"))

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
        "products": products,
        "products_done": products_done,
        "products_total": len(products),
        "design_status": production_status,
        "design_status_label": PRODUCTION_STATUS_LABELS.get(production_status, production_status),
        "assigned_to": _assigned_label_from_po(po, tracking),
        "assigned_to_user_id": _assigned_user_id(po, tracking),
        "can_claim": _assigned_user_id(po, tracking) is None
        and production_status in DESIGN_PHASE_FILTER,
        "production_status": production_status,
        "design_urls": [d["url"] for d in designs] or (get_design_urls(quotation) if quotation else []),
        "designs": designs,
        "designs_count": len(designs),
        "max_designs": MAX_QUOTATION_DESIGNS,
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


def list_shipping_queue(db: Session) -> list[dict[str, Any]]:
    """Órdenes en envío, para imprimir los despachos del día."""
    from datetime import date as date_cls

    from app.services.shipment_service import get_latest_shipment

    today = date_cls.today()
    orders = (
        db.query(ProductionOrder)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client),
            joinedload(ProductionOrder.quotation)
            .joinedload(Quotation.items)
            .joinedload(QuotationItem.product),
        )
        .all()
    )
    rows: list[dict[str, Any]] = []
    for order in orders:
        if normalize_status(order.status) != "envio":
            continue
        quotation = order.quotation
        client = quotation.client if quotation else None
        shipment = get_latest_shipment(db, quotation.id) if quotation else None
        delivery = quotation.delivery_date if quotation else None
        rows.append(
            {
                "order_id": order.id,
                "order_label": f"OP-{order.id:04d}",
                "quotation_id": quotation.id if quotation else None,
                "client_name": client.name if client else "—",
                "delivery_date": delivery,
                "is_today": delivery == today,
                "notes": order.design_notes or "",
                "products": work_items_payload(quotation),
                "guide_number": shipment.guide_number if shipment else None,
                "shipment_id": shipment.id if shipment else None,
            }
        )
    rows.sort(
        key=lambda row: (
            not row["is_today"],
            row["delivery_date"] is None,
            row["delivery_date"] or today,
            row["quotation_id"] or 0,
        )
    )
    return rows


def list_designers(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == "disenador", User.active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )


def send_quotation_to_design(
    db: Session,
    quotation: Quotation,
    *,
    designer_user_id: int,
    actor: User | None = None,
    note: str = "",
) -> ProductionOrder:
    """Desde cotización aprobada: crea/asegura OP, asigna diseñador y pasa a fase diseño."""
    q_status = (quotation.status or "").lower().strip()
    if q_status not in {"aprobada", "produccion"}:
        raise ValueError("Solo cotizaciones aprobadas pueden enviarse a diseño.")

    designer = (
        db.query(User)
        .filter(
            User.id == designer_user_id,
            User.role == "disenador",
            User.active.is_(True),
        )
        .first()
    )
    if not designer:
        raise ValueError("Seleccione un diseñador válido.")

    order = get_production_order_by_quotation(db, quotation.id)
    if not order:
        order = ensure_production_order(
            db,
            quotation,
            user_id=actor.id if actor else None,
        )
        db.flush()
    if not order:
        raise ValueError("No se pudo crear la orden de producción.")

    current = normalize_status(order.status)
    if current not in DESIGN_PHASE_FILTER:
        raise ValueError(
            "La orden ya avanzó de diseño. No se puede reasignar desde cotización."
        )

    designer_label = designer.full_name or designer.username
    order.assigned_to_user_id = designer.id
    order.designer = designer_label
    order.updated_at = datetime.utcnow()

    history_note = (note or "").strip() or f"Enviado a diseño — asignado a {designer_label}"

    if current == "pendiente":
        transition_status(
            db,
            order,
            "diseno",
            user=actor,
            notes=history_note,
        )
    else:
        from app.services.production_order_service import log_history

        log_history(
            db,
            order,
            status=current,
            notes=history_note,
            user_id=actor.id if actor else None,
        )
        db.commit()
        db.refresh(order)

    # Sincronizar tracking de ítems de diseño (excluye transporte)
    items = (
        db.query(QuotationItem)
        .options(joinedload(QuotationItem.product), joinedload(QuotationItem.design_tracking))
        .filter(QuotationItem.quotation_id == quotation.id)
        .all()
    )
    for item in items:
        if not item_needs_design(item):
            continue
        tracking = item.design_tracking or get_or_create_design_tracking(db, item.id)
        tracking.assigned_to_user_id = designer.id
        tracking.assigned_to = designer_label
        tracking.status = "en_diseno"
        tracking.updated_at = datetime.utcnow()
        _add_observation(
            db,
            tracking,
            user=actor,
            note=history_note,
        )

    db.commit()
    return get_production_order_by_quotation(db, quotation.id) or order
