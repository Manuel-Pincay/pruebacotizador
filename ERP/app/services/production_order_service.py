"""Flujo unificado: 1 cotización → 1 orden de producción."""

from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session, joinedload

from app.models.production_order import ProductionOrder
from app.models.production_order_history import ProductionOrderHistory
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.user import User

PRODUCTION_ORDER_STATUSES: list[tuple[str, str]] = [
    ("pendiente", "Pendiente"),
    ("diseno", "Diseño"),
    ("produccion", "Producción"),
    ("envio", "Envío"),
    ("entregado", "Entregado"),
    ("cancelado", "Cancelado"),
]

PRODUCTION_STATUS_LABELS = dict(PRODUCTION_ORDER_STATUSES)
PRODUCTION_STATUS_SEQUENCE = [code for code, _ in PRODUCTION_ORDER_STATUSES if code != "cancelado"]

DESIGN_PHASE_STATUSES = {"pendiente", "diseno"}
DESIGN_EDIT_STATUSES = {"pendiente", "diseno"}

DESIGN_MATERIALS = ["MDF", "Acrílico", "PVC", "Cartón", "Vinil", "Foami", "Otro"]
DESIGN_SIZES = ["120x90", "50x100", "10x10", "Retazo", "Plancha Completa", "A4", "A3"]
USB_REFERENCES = ["USB #1", "USB #2", "USB Azul", "USB Rojo", "USB Producción"]

LEGACY_STATUS_MAP = {
    "pendiente_diseno": "pendiente",
    "en_diseno": "diseno",
    "diseno_aprobado": "diseno",
    "pendiente_produccion": "produccion",
    "en_produccion": "produccion",
    "empaque": "produccion",
    "listo_despacho": "envio",
    "despachado": "envio",
    "enviado": "envio",
    "diseño": "diseno",
    "empacado": "produccion",
    "control_calidad": "produccion",
    "listo": "envio",
    "cancelada": "cancelado",
}

PRODUCTION_STATUS_COLORS = {
    "pendiente": "gray",
    "diseno": "indigo",
    "produccion": "purple",
    "envio": "blue",
    "entregado": "green",
    "cancelado": "red",
}


def parse_design_file_names(value: str | None) -> list[str]:
    """Separa nombres de archivo guardados en una sola columna (uno por línea)."""
    if not value or not str(value).strip():
        return []
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    names: list[str] = []
    for line in text.split("\n"):
        part = line.strip()
        if part:
            names.append(part)
    return names


def join_design_file_names(names: list[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for name in names:
        part = (name or "").strip()
        if part and part not in seen:
            seen.add(part)
            cleaned.append(part)
    return "\n".join(cleaned)


def format_design_file_names_display(value: str | None) -> str:
    return ", ".join(parse_design_file_names(value))


def _clean_file_spec_row(row: dict | None) -> dict[str, str]:
    data = row if isinstance(row, dict) else {}
    return {
        "file_name": str(data.get("file_name") or "").strip(),
        "material": str(data.get("material") or "").strip(),
        "size": str(data.get("size") or "").strip(),
    }


def normalize_file_specs(specs: list[dict] | None) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in specs or []:
        spec = _clean_file_spec_row(row)
        if not spec["file_name"]:
            continue
        key = spec["file_name"].lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(spec)
    return cleaned


def parse_design_file_specs(order: ProductionOrder) -> list[dict[str, str]]:
    """Lista de {file_name, material, size} por archivo físico."""
    if order.design_file_specs:
        try:
            raw = json.loads(order.design_file_specs)
            if isinstance(raw, list):
                return normalize_file_specs(raw)
        except (json.JSONDecodeError, TypeError):
            pass

    names = parse_design_file_names(order.design_file_name)
    legacy_material = (order.design_material or "").strip()
    legacy_size = (order.design_size or "").strip()
    if not names:
        if legacy_material or legacy_size:
            return [{"file_name": "", "material": legacy_material, "size": legacy_size}]
        return []
    return [
        {"file_name": name, "material": legacy_material, "size": legacy_size}
        for name in names
    ]


def serialize_design_file_specs(specs: list[dict] | None) -> str | None:
    cleaned = normalize_file_specs(specs)
    if not cleaned:
        return None
    return json.dumps(cleaned, ensure_ascii=False)


def parse_file_specs_from_form(form) -> list[dict[str, str]]:
    names = form.getlist("spec_file_name")
    materials = form.getlist("spec_material")
    sizes = form.getlist("spec_size")
    specs: list[dict[str, str]] = []
    for index, name in enumerate(names):
        material = (materials[index] if index < len(materials) else "").strip()
        size = (sizes[index] if index < len(sizes) else "").strip()
        part = (name or "").strip()
        if part or material or size:
            specs.append({"file_name": part, "material": material, "size": size})
    return specs


def sync_legacy_fields_from_specs(order: ProductionOrder, specs: list[dict[str, str]]) -> None:
    cleaned = normalize_file_specs(specs)
    order.design_file_specs = serialize_design_file_specs(cleaned)
    order.design_file_name = join_design_file_names([row["file_name"] for row in cleaned]) or None
    if not cleaned:
        return

    materials = [row["material"] for row in cleaned if row["material"]]
    sizes = [row["size"] for row in cleaned if row["size"]]
    unique_materials = list(dict.fromkeys(materials))
    unique_sizes = list(dict.fromkeys(sizes))
    order.design_material = (
        unique_materials[0]
        if len(unique_materials) == 1
        else "; ".join(unique_materials) if unique_materials else None
    )
    order.design_size = (
        unique_sizes[0]
        if len(unique_sizes) == 1
        else "; ".join(unique_sizes) if unique_sizes else None
    )


def fabrication_data_complete(order: ProductionOrder) -> bool:
    specs = parse_design_file_specs(order)
    if specs:
        return bool(
            all(row["file_name"] and row["material"] and row["size"] for row in specs)
            and (order.design_copies or 0) > 0
        )
    return bool(
        parse_design_file_names(order.design_file_name)
        and (order.design_material or "").strip()
        and (order.design_size or "").strip()
        and (order.design_copies or 0) > 0
    )


def validate_fabrication_data(order: ProductionOrder) -> None:
    specs = parse_design_file_specs(order)
    if specs:
        missing: list[str] = []
        for index, row in enumerate(specs, start=1):
            label = row["file_name"] or f"#{index}"
            if not row["file_name"]:
                missing.append(f"archivo ({label})")
            if not row["material"]:
                missing.append(f"material de {label}")
            if not row["size"]:
                missing.append(f"medida de {label}")
        if not (order.design_copies or 0):
            missing.append("copias")
        if missing:
            raise ValueError(f"Complete datos de fabricación: {', '.join(missing)}.")
        return

    missing = []
    if not parse_design_file_names(order.design_file_name):
        missing.append("archivo")
    if not (order.design_material or "").strip():
        missing.append("material")
    if not (order.design_size or "").strip():
        missing.append("medida")
    if not (order.design_copies or 0):
        missing.append("copias")
    if missing:
        raise ValueError(f"Complete datos de fabricación: {', '.join(missing)}.")


def normalize_status(status: str | None) -> str:
    code = (status or "pendiente").lower().strip()
    mapped = LEGACY_STATUS_MAP.get(code, code)
    if mapped in PRODUCTION_STATUS_LABELS:
        return mapped
    return "pendiente"


def _user_label(user: User | None) -> str:
    if not user:
        return "—"
    return user.full_name or user.username or "—"


def _work_quotation_items(quotation: Quotation):
    from app.services.transport_product_service import is_transport_quotation_item

    items = []
    for item in quotation.items or []:
        if is_transport_quotation_item(item):
            continue
        items.append(item)
    return items


def quotation_needs_fabrication(quotation: Quotation | None) -> bool:
    """True si algún ítem de trabajo no sale de inventario terminado."""
    if not quotation:
        return True
    items = _work_quotation_items(quotation)
    if not items:
        return False
    return any(not bool(getattr(item, "fulfill_from_inventory", False)) for item in items)


def _item_image_urls(item) -> tuple[str | None, str | None]:
    from app.utils.image_storage import product_image_url

    image_name = (getattr(item, "product_image", None) or "").strip()
    product = getattr(item, "product", None)
    if not image_name and product:
        image_name = (product.image or "").strip()
    if not image_name:
        return None, None
    full = product_image_url(image_name, thumb=False)
    thumb = product_image_url(image_name, thumb=True) or full
    return full, thumb


def work_items_payload(quotation: Quotation | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not quotation:
        return rows
    for item in _work_quotation_items(quotation):
        product = item.product
        name = (item.detail or "").strip() or (product.name if product else "—")
        image_url, image_thumb_url = _item_image_urls(item)
        rows.append(
            {
                "id": item.id,
                "name": name,
                "quantity": item.quantity or 0,
                "measure": item.measure or "—",
                "theme": item.theme or "—",
                "color": item.color or "—",
                "product_id": item.product_id,
                "stock": product.stock if product else None,
                "fulfill_from_inventory": bool(getattr(item, "fulfill_from_inventory", False)),
                "design_item_done": bool(getattr(item, "design_item_done", False)),
                "image_url": image_url,
                "image_thumb_url": image_thumb_url,
            }
        )
    return rows


def apply_quotation_item_fulfillment(quotation: Quotation | None, form_data) -> None:
    """Lee fulfill_item_{id} y done_item_{id} del formulario."""
    if not quotation:
        return
    for item in _work_quotation_items(quotation):
        mode = str(form_data.get(f"fulfill_item_{item.id}") or "").strip().lower()
        if mode in {"inventory", "inventario", "1", "true", "on"}:
            item.fulfill_from_inventory = True
        elif mode in {"production", "produccion", "0"}:
            item.fulfill_from_inventory = False
        done_raw = form_data.get(f"done_item_{item.id}")
        if done_raw is not None:
            item.design_item_done = str(done_raw).strip().lower() in {"1", "on", "true", "yes"}


def _already_deducted_for_item(db: Session, quotation_id: int, item_id: int) -> bool:
    from app.models.inventory_movement import InventoryMovement

    marker = f"Cotización #{quotation_id} ítem {item_id} "
    row = (
        db.query(InventoryMovement.id)
        .filter(InventoryMovement.reason.contains(marker))
        .first()
    )
    return row is not None


def _deduct_inventory_for_quotation(db: Session, quotation: Quotation, *, only_flagged: bool = True) -> None:
    from app.models.inventory_movement import InventoryMovement
    from app.models.product import Product

    if not quotation or not quotation.items:
        return
    for item in _work_quotation_items(quotation):
        if only_flagged and not bool(getattr(item, "fulfill_from_inventory", False)):
            continue
        if not item.product_id:
            continue
        if _already_deducted_for_item(db, quotation.id, item.id):
            continue
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            continue
        previous_stock = product.stock or 0
        qty = int(item.quantity or 0)
        new_stock = previous_stock - qty
        if new_stock < 0:
            raise ValueError(
                f"Stock insuficiente para {product.name}. "
                f"Disponible: {previous_stock}, solicitado: {qty}."
            )
        product.stock = new_stock
        db.add(
            InventoryMovement(
                product_id=product.id,
                movement_type="salida",
                quantity=-qty,
                previous_stock=previous_stock,
                new_stock=new_stock,
                reason=f"Cotización #{quotation.id} ítem {item.id} producto {product.id} → Inventario diseño",
            )
        )


def log_history(
    db: Session,
    order: ProductionOrder,
    *,
    status: str,
    notes: str = "",
    user_id: int | None = None,
) -> ProductionOrderHistory:
    entry = ProductionOrderHistory(
        production_order_id=order.id,
        status=normalize_status(status),
        notes=notes.strip() or None,
        created_by=user_id,
    )
    db.add(entry)
    return entry


def can_transition(current: str | None, target: str) -> bool:
    current_code = normalize_status(current)
    target_code = normalize_status(target)
    if target_code == "cancelado":
        return current_code != "entregado"
    if current_code == "cancelado":
        return False
    # Inventario listo: diseño puede ir directo a envío (sin fabricación).
    if current_code in DESIGN_PHASE_STATUSES and target_code == "envio":
        return True
    try:
        return PRODUCTION_STATUS_SEQUENCE.index(target_code) == PRODUCTION_STATUS_SEQUENCE.index(current_code) + 1
    except ValueError:
        return False


def ensure_production_order(
    db: Session,
    quotation: Quotation,
    *,
    user_id: int | None = None,
) -> ProductionOrder | None:
    q_status = (quotation.status or "").lower().strip()
    if q_status in ("pendiente", "cancelada", "cancelado", "borrador", "vencida"):
        return None

    existing = db.query(ProductionOrder).filter(ProductionOrder.quotation_id == quotation.id).first()
    if existing:
        existing.status = normalize_status(existing.status)
        return existing

    order = ProductionOrder(
        quotation_id=quotation.id,
        delivery_date=quotation.delivery_date,
        priority="media",
        status="pendiente",
        observations="",
        design_copies=1,
    )
    db.add(order)
    db.flush()
    log_history(db, order, status="pendiente", notes="Orden creada al aprobar cotización.", user_id=user_id)
    return order


def get_production_order(db: Session, order_id: int) -> ProductionOrder | None:
    return (
        db.query(ProductionOrder)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client),
            joinedload(ProductionOrder.quotation)
            .joinedload(Quotation.items)
            .joinedload(QuotationItem.product),
            joinedload(ProductionOrder.quotation).joinedload(Quotation.designs),
            joinedload(ProductionOrder.history).joinedload(ProductionOrderHistory.author),
            joinedload(ProductionOrder.assignee),
            joinedload(ProductionOrder.design_completer),
            joinedload(ProductionOrder.raw_material),
        )
        .filter(ProductionOrder.id == order_id)
        .first()
    )


def get_production_order_by_quotation(db: Session, quotation_id: int) -> ProductionOrder | None:
    return (
        db.query(ProductionOrder)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client),
            joinedload(ProductionOrder.assignee),
            joinedload(ProductionOrder.history).joinedload(ProductionOrderHistory.author),
        )
        .filter(ProductionOrder.quotation_id == quotation_id)
        .first()
    )


def transition_status(
    db: Session,
    order: ProductionOrder,
    new_status: str,
    *,
    user: User | None = None,
    notes: str = "",
    force: bool = False,
) -> ProductionOrder:
    target = normalize_status(new_status)
    current = normalize_status(order.status)

    if not force and not can_transition(current, target):
        if not (target == "cancelado" and user and user.role == "admin"):
            raise ValueError(
                f"No se puede pasar de {PRODUCTION_STATUS_LABELS.get(current, current)} "
                f"a {PRODUCTION_STATUS_LABELS.get(target, target)}."
            )

    now = datetime.utcnow()
    if not order.started_at and target != "pendiente":
        order.started_at = now
    if target == "entregado":
        order.completed_at = now

    quotation = order.quotation
    leaving_design = normalize_status(order.status) in DESIGN_PHASE_STATUSES and target in {
        "produccion",
        "envio",
    }
    if leaving_design:
        if target == "produccion" and quotation_needs_fabrication(quotation):
            validate_fabrication_data(order)
        order.design_completed_at = now
        order.design_completed_by = user.id if user else None

    if target == "produccion":
        if order.use_fabrication_materials:
            from app.services.raw_material_service import consume_for_production

            consume_for_production(db, order, user_id=user.id if user else None)
        if quotation:
            # Ítems marcados inventario siempre se descuentan.
            # Si no usa materia prima, también descuenta el resto (stock terminado).
            _deduct_inventory_for_quotation(
                db,
                quotation,
                only_flagged=bool(order.use_fabrication_materials),
            )
    elif target == "envio" and quotation:
        _deduct_inventory_for_quotation(db, quotation, only_flagged=True)

    order.status = target
    order.updated_at = now
    log_history(db, order, status=target, notes=notes, user_id=user.id if user else None)

    if quotation:
        if target == "produccion":
            quotation.status = "produccion"
        elif target == "envio":
            quotation.status = "enviado"
        elif target == "entregado":
            quotation.status = "entregado"
        elif target == "cancelado":
            quotation.status = "cancelada"

    db.commit()
    db.refresh(order)
    if current != target:
        try:
            from app.services.notification_service import NotificationService

            client_name = "—"
            if quotation and quotation.client:
                client_name = quotation.client.name or "—"
            user_name = "—"
            if user:
                user_name = (user.full_name or user.username or "—").strip() or "—"
            order_label = f"OP-{order.id:04d}"
            if target == "entregado":
                NotificationService.notify_order_delivered(
                    client=client_name,
                    order_id=order_label,
                    delivered_at=order.completed_at,
                )
            else:
                NotificationService.notify_order_status_changed(
                    client=client_name,
                    order_id=order_label,
                    from_status=PRODUCTION_STATUS_LABELS.get(current, current),
                    to_status=PRODUCTION_STATUS_LABELS.get(target, target),
                    status_code=target,
                    user=user_name,
                    quotation_id=quotation.id if quotation else None,
                )
        except Exception:
            pass
    return order


def update_design_fields(
    db: Session,
    order: ProductionOrder,
    *,
    file_name: str | None = None,
    file_specs: list[dict] | None = None,
    material: str = "",
    size: str = "",
    usb_reference: str = "",
    notes: str = "",
    copies: int = 1,
    user: User | None = None,
    use_fabrication_materials: bool | None = None,
    raw_material_id: int | None = None,
    raw_material_qty: float | None = None,
    raw_material_items: list[dict] | None = None,
) -> ProductionOrder:
    if file_specs is not None:
        sync_legacy_fields_from_specs(order, file_specs)
    elif file_name is not None:
        order.design_file_name = join_design_file_names(parse_design_file_names(file_name)) or None
        if material:
            order.design_material = material.strip()
        if size:
            order.design_size = size.strip()

    if file_specs is None and material:
        if material not in DESIGN_MATERIALS:
            raise ValueError("Material no válido.")
        order.design_material = material.strip()
    if file_specs is None and size:
        order.design_size = size.strip()
    order.design_usb_reference = usb_reference.strip() or None
    order.design_notes = notes.strip() or None
    order.design_copies = max(1, int(copies or 1))
    order.updated_at = datetime.utcnow()

    if use_fabrication_materials is not None:
        from app.services.raw_material_service import set_fabrication_source

        set_fabrication_source(
            db,
            order,
            use_fabrication_materials=use_fabrication_materials,
            raw_material_id=raw_material_id,
            raw_material_qty=raw_material_qty,
            raw_material_items=raw_material_items,
        )

    current = normalize_status(order.status)
    if current == "pendiente":
        transition_status(db, order, "diseno", user=user, notes="Inicio de diseño.")
    else:
        db.commit()
        db.refresh(order)
    return order


def approve_design(
    db: Session,
    order: ProductionOrder,
    *,
    user: User | None = None,
    notes: str = "",
    use_fabrication_materials: bool | None = None,
    raw_material_id: int | None = None,
    raw_material_qty: float | None = None,
    raw_material_items: list[dict] | None = None,
) -> ProductionOrder:
    current = normalize_status(order.status)
    if current not in DESIGN_EDIT_STATUSES:
        raise ValueError("La orden no está en fase de diseño.")

    work_items = _work_quotation_items(order.quotation) if order.quotation else []
    if work_items and not all(bool(getattr(item, "design_item_done", False)) for item in work_items):
        raise ValueError("Marque cada producto como listo antes de enviar la orden.")

    needs_fab = quotation_needs_fabrication(order.quotation)
    if not needs_fab:
        use_fabrication_materials = False
        raw_material_id = None
        raw_material_qty = None
        raw_material_items = None
    if needs_fab:
        validate_fabrication_data(order)

    if use_fabrication_materials is not None:
        from app.services.raw_material_service import set_fabrication_source

        set_fabrication_source(
            db,
            order,
            use_fabrication_materials=use_fabrication_materials,
            raw_material_id=raw_material_id,
            raw_material_qty=raw_material_qty,
            raw_material_items=raw_material_items,
        )

    if current == "pendiente":
        transition_status(db, order, "diseno", user=user, notes="Inicio de diseño.")
        order = get_production_order(db, order.id) or order

    fab_note = ""
    if needs_fab and order.use_fabrication_materials:
        from app.services.raw_material_service import parse_fabrication_raw_materials

        rows = parse_fabrication_raw_materials(order)
        if rows:
            parts = [
                f"{row.get('label') or 'Materia prima'} ({float(row['qty']):g} {row.get('unit') or ''})".strip()
                for row in rows
            ]
            fab_note = " Material de fabricación: " + "; ".join(parts) + "."

    if needs_fab:
        target = "produccion"
        default_notes = "Datos de fabricación listos — pasa a producción."
    else:
        target = "envio"
        default_notes = "Productos de inventario — pasa a envío (sin fabricación)."

    transition_status(
        db,
        order,
        target,
        user=user,
        notes=(notes or default_notes) + fab_note,
    )
    return get_production_order(db, order.id) or order


def assign_designer(db: Session, order: ProductionOrder, designer_user_id: int | None) -> ProductionOrder:
    designer = db.query(User).filter(User.id == designer_user_id).first() if designer_user_id else None
    order.assigned_to_user_id = designer.id if designer else None
    order.designer = _user_label(designer) if designer else None
    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return order


def claim_design_order(db: Session, order: ProductionOrder, *, user: User) -> ProductionOrder:
    """Diseñador se marca responsable. No excluye a otros; solo registra quién lidera."""
    if not user or user.role != "disenador":
        raise ValueError("Solo un diseñador puede tomarse esta orden.")
    if normalize_status(order.status) not in DESIGN_EDIT_STATUSES:
        raise ValueError("Solo se pueden tomar órdenes en fase de diseño.")
    previous = order.assigned_to_user_id
    if previous == user.id:
        return order
    assign_designer(db, order, user.id)
    if previous:
        notes = f"{_user_label(user)} se marcó responsable (antes otro diseñador)."
    else:
        notes = f"Diseñador se autoasignó: {_user_label(user)}"
    log_history(
        db,
        order,
        status=normalize_status(order.status),
        notes=notes,
        user_id=user.id,
    )
    db.commit()
    db.refresh(order)
    return order


def list_assignable_designers(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == "disenador", User.active.is_(True))
        .order_by(User.full_name.asc(), User.username.asc())
        .all()
    )


def list_assignable_fabricators(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == "produccion", User.active.is_(True))
        .order_by(User.full_name.asc(), User.username.asc())
        .all()
    )


def _match_user_id_by_label(db: Session, label: str | None, role: str) -> int | None:
    text = (label or "").strip()
    if not text:
        return None
    lowered = text.lower()
    for user in db.query(User).filter(User.role == role, User.active.is_(True)).all():
        candidates = {
            (user.full_name or "").strip().lower(),
            (user.username or "").strip().lower(),
            _user_label(user).lower(),
        }
        if lowered in candidates:
            return user.id
    return None


def resolve_selected_designer_id(order: ProductionOrder, db: Session) -> int | None:
    if order.assigned_to_user_id:
        return order.assigned_to_user_id
    return _match_user_id_by_label(db, order.designer, "disenador")


def resolve_selected_fabricator_id(order: ProductionOrder, db: Session) -> int | None:
    return _match_user_id_by_label(db, order.fabricator, "produccion")


def apply_designer_assignment(
    order: ProductionOrder,
    db: Session,
    designer_user_id: int | None,
) -> None:
    if not designer_user_id:
        order.assigned_to_user_id = None
        order.designer = None
        return
    designer = (
        db.query(User)
        .filter(User.id == designer_user_id, User.role == "disenador", User.active.is_(True))
        .first()
    )
    if not designer:
        return
    order.assigned_to_user_id = designer.id
    order.designer = _user_label(designer)


def apply_fabricator_assignment(
    order: ProductionOrder,
    db: Session,
    fabricator_user_id: int | None,
) -> None:
    if not fabricator_user_id:
        order.fabricator = None
        return
    fabricator = (
        db.query(User)
        .filter(User.id == fabricator_user_id, User.role == "produccion", User.active.is_(True))
        .first()
    )
    if not fabricator:
        return
    order.fabricator = _user_label(fabricator)


def list_design_orders(
    db: Session,
    *,
    viewer_user_id: int | None = None,
    admin_view: bool = False,
) -> list[dict[str, Any]]:
    query = (
        db.query(ProductionOrder)
        .join(Quotation, ProductionOrder.quotation_id == Quotation.id)
        .options(
            joinedload(ProductionOrder.quotation).joinedload(Quotation.client),
            joinedload(ProductionOrder.assignee),
        )
        .order_by(ProductionOrder.created_at.desc())
    )
    if not admin_view and viewer_user_id:
        query = query.filter(
            (ProductionOrder.assigned_to_user_id.is_(None))
            | (ProductionOrder.assigned_to_user_id == viewer_user_id)
        )

    rows: list[dict[str, Any]] = []
    for order in query.all():
        if normalize_status(order.status) not in DESIGN_PHASE_STATUSES:
            continue
        client = order.quotation.client if order.quotation else None
        rows.append(build_order_dict(order, client_name=client.name if client else "—"))
    return rows


def build_order_dict(order: ProductionOrder, *, client_name: str = "—") -> dict[str, Any]:
    status = normalize_status(order.status)
    file_names = parse_design_file_names(order.design_file_name)
    file_specs = parse_design_file_specs(order)
    from app.services.raw_material_service import parse_fabrication_raw_materials

    raw_material_items = parse_fabrication_raw_materials(order)
    raw_labels = [
        f"{row.get('label') or 'Materia prima'} ({float(row['qty']):g} {row.get('unit') or ''})".strip()
        for row in raw_material_items
    ]
    return {
        "id": order.id,
        "order_label": f"OP-{order.id:04d}",
        "quotation_id": order.quotation_id,
        "client_name": client_name,
        "file_names": file_names,
        "file_specs": file_specs,
        "file_name": order.design_file_name or "",
        "file_name_display": format_design_file_names_display(order.design_file_name),
        "material": order.design_material or "",
        "size": order.design_size or "",
        "usb_reference": order.design_usb_reference or "",
        "detail": order.design_notes or "",
        "copies": order.design_copies or 1,
        "status": status,
        "status_label": PRODUCTION_STATUS_LABELS.get(status, status),
        "assigned_to": order.assigned_to_user_id,
        "assigned_to_name": _user_label(order.assignee),
        "created_at": order.created_at,
        "use_fabrication_materials": bool(order.use_fabrication_materials),
        "raw_material_id": order.raw_material_id,
        "raw_material_qty": float(order.raw_material_qty) if order.raw_material_qty is not None else None,
        "raw_material_label": order.raw_material.label if order.raw_material else "",
        "raw_material_items": raw_material_items,
        "raw_material_labels": raw_labels,
        "raw_material_display": "; ".join(raw_labels),
    }


def build_history_list(order: ProductionOrder) -> list[dict[str, Any]]:
    return [
        {
            "status_label": PRODUCTION_STATUS_LABELS.get(normalize_status(entry.status), entry.status),
            "notes": entry.notes or "",
            "created_by_name": _user_label(entry.author),
            "created_at": entry.created_at,
        }
        for entry in sorted(order.history or [], key=lambda row: row.created_at or datetime.min)
    ]


class _NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.setFont("Helvetica", 5)
            self.drawRightString(200 * mm, 5 * mm, f"Pág. {self._pageNumber} de {total}")
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


def export_design_sheet_pdf(order_dict: dict[str, Any], products: list[dict[str, Any]] | None = None) -> BytesIO:
    margin = 8 * mm
    page_width, _ = A4
    usable = page_width - 2 * margin
    cell = ParagraphStyle("Cell", fontName="Helvetica", fontSize=6, leading=7, alignment=TA_LEFT)
    cell_center = ParagraphStyle("CellC", parent=cell, alignment=TA_CENTER)
    title = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=8, leading=9, alignment=TA_LEFT)
    section = ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=7, leading=8, alignment=TA_LEFT)

    header = (
        f"<b>ORDEN DE PRODUCCIÓN {order_dict['order_label']}</b> | "
        f"Cot. #{order_dict.get('quotation_id')}"
    )

    story: list[Any] = [Paragraph(header, title), Spacer(1, 2 * mm)]

    items = products if products is not None else list(order_dict.get("products") or [])
    to_fabricate = [p for p in items if not p.get("fulfill_from_inventory")]
    from_inventory = [p for p in items if p.get("fulfill_from_inventory")]
    product_rows = to_fabricate or items

    if product_rows:
        story.append(Paragraph("<b>PRODUCTOS A FABRICAR</b>", section))
        story.append(Spacer(1, 1 * mm))
        prod_data = [
            [
                Paragraph("<b>Producto</b>", cell_center),
                Paragraph("<b>Cant.</b>", cell_center),
                Paragraph("<b>Medida</b>", cell_center),
                Paragraph("<b>Tema</b>", cell_center),
                Paragraph("<b>Color</b>", cell_center),
                Paragraph("<b>Origen</b>", cell_center),
            ]
        ]
        for p in product_rows:
            origin = "Inventario" if p.get("fulfill_from_inventory") else "Fabricar"
            prod_data.append(
                [
                    Paragraph(str(p.get("name") or "—")[:40], cell),
                    Paragraph(str(p.get("quantity") or 0), cell_center),
                    Paragraph(str(p.get("measure") or "—")[:16], cell_center),
                    Paragraph(str(p.get("theme") or "—")[:16], cell_center),
                    Paragraph(str(p.get("color") or "—")[:12], cell_center),
                    Paragraph(origin, cell_center),
                ]
            )
        prod_table = Table(prod_data, colWidths=[usable * r for r in [0.34, 0.08, 0.14, 0.16, 0.12, 0.16]])
        prod_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E7FF")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.extend([prod_table, Spacer(1, 3 * mm)])

        if to_fabricate and from_inventory:
            inv_lines = ", ".join(
                f"{p.get('name') or '—'} (x{p.get('quantity') or 0})" for p in from_inventory
            )
            story.append(Paragraph(f"<b>Inventario:</b> {inv_lines}", cell))
            story.append(Spacer(1, 2 * mm))

    story.append(Paragraph("<b>DATOS DE FABRICACIÓN</b>", section))
    story.append(Spacer(1, 1 * mm))

    file_specs = list(order_dict.get("file_specs") or [])
    table_data = [
        [
            Paragraph("<b>Archivo</b>", cell_center),
            Paragraph("<b>Material</b>", cell_center),
            Paragraph("<b>Medida</b>", cell_center),
            Paragraph("<b>USB</b>", cell_center),
            Paragraph("<b>Cant.</b>", cell_center),
            Paragraph("<b>Cliente</b>", cell_center),
        ],
    ]
    if file_specs:
        for index, spec in enumerate(file_specs):
            table_data.append(
                [
                    Paragraph(spec.get("file_name") or "—", cell),
                    Paragraph(spec.get("material") or "—", cell),
                    Paragraph(spec.get("size") or "—", cell_center),
                    Paragraph(order_dict.get("usb_reference") or "—", cell_center) if index == 0 else Paragraph("", cell_center),
                    Paragraph(str(order_dict.get("copies") or 0), cell_center) if index == 0 else Paragraph("", cell_center),
                    Paragraph((order_dict.get("client_name") or "—")[:24], cell) if index == 0 else Paragraph("", cell),
                ]
            )
    else:
        table_data.append(
            [
                Paragraph("<br/>".join(parse_design_file_names(order_dict.get("file_name"))) or "—", cell),
                Paragraph(order_dict.get("material") or "—", cell_center),
                Paragraph(order_dict.get("size") or "—", cell_center),
                Paragraph(order_dict.get("usb_reference") or "—", cell_center),
                Paragraph(str(order_dict.get("copies") or 0), cell_center),
                Paragraph((order_dict.get("client_name") or "—")[:24], cell),
            ]
        )
    if order_dict.get("detail"):
        table_data.append([Paragraph(f"<b>Obs:</b> {order_dict['detail']}", cell), "", "", "", "", ""])

    table = Table(table_data, colWidths=[usable * r for r in [0.28, 0.12, 0.12, 0.12, 0.08, 0.28]])
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if order_dict.get("detail"):
        style_cmds.append(("SPAN", (0, -1), (-1, -1)))
    table.setStyle(TableStyle(style_cmds))
    story.append(table)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=10 * mm, canvasmaker=_NumberedCanvas)
    doc.build(story)
    buffer.seek(0)
    return buffer
