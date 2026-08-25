"""Inventario de materia prima (planchas / vinil) y consumo en producción."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.production_order import ProductionOrder
from app.models.raw_material import RawMaterial
from app.models.raw_material_movement import RawMaterialMovement

MATERIAL_KINDS = [
    {"value": "plancha", "label": "Plancha", "unit": "planchas"},
    {"value": "vinil", "label": "Vinil", "unit": "metros"},
]

MATERIAL_TYPES = [
    "MDF",
    "Acrílico",
    "Vinil",
    "PVC",
    "Cartón",
    "Foami",
    "Otro",
]

# Mapeo design_material de OP → tipos de materia prima sugeridos
DESIGN_TO_RAW_TYPES = {
    "mdf": ["MDF"],
    "acrílico": ["Acrílico"],
    "acrilico": ["Acrílico"],
    "pvc": ["PVC"],
    "cartón": ["Cartón"],
    "carton": ["Cartón"],
    "vinil": ["Vinil"],
    "foami": ["Foami"],
}


def list_raw_materials(
    db: Session,
    *,
    kind: str | None = None,
    active_only: bool = True,
    low_stock_only: bool = False,
) -> list[RawMaterial]:
    q = db.query(RawMaterial)
    if active_only:
        q = q.filter(RawMaterial.active.is_(True))
    if kind:
        q = q.filter(RawMaterial.kind == kind)
    materials = q.order_by(RawMaterial.kind.asc(), RawMaterial.material_type.asc(), RawMaterial.name.asc()).all()
    if low_stock_only:
        materials = [m for m in materials if m.is_low_stock]
    return materials


def count_low_stock(db: Session) -> int:
    return sum(1 for m in list_raw_materials(db, active_only=True) if m.is_low_stock)


def get_raw_material(db: Session, material_id: int) -> RawMaterial | None:
    return db.query(RawMaterial).filter(RawMaterial.id == material_id).first()


def materials_for_design(db: Session, design_material: str | None = None) -> list[RawMaterial]:
    materials = list_raw_materials(db, active_only=True)
    if not design_material:
        return materials
    key = design_material.strip().lower()
    allowed = DESIGN_TO_RAW_TYPES.get(key)
    if not allowed:
        return materials
    filtered = [m for m in materials if m.material_type in allowed]
    return filtered or materials


def create_raw_material(
    db: Session,
    *,
    kind: str,
    material_type: str,
    name: str,
    size: str = "",
    thickness: str = "",
    color: str = "",
    stock: float = 0,
    min_stock: float = 0,
    notes: str = "",
    user_id: int | None = None,
) -> RawMaterial:
    kind = (kind or "plancha").strip().lower()
    if kind not in ("plancha", "vinil"):
        raise ValueError("Tipo de materia prima inválido (plancha o vinil).")
    name = (name or "").strip()
    if not name:
        raise ValueError("Ingrese el nombre de la materia prima.")
    material_type = (material_type or "").strip()
    if not material_type:
        raise ValueError("Seleccione el tipo de material.")

    unit = "metros" if kind == "vinil" else "planchas"
    initial = float(stock or 0)
    material = RawMaterial(
        kind=kind,
        material_type=material_type,
        name=name,
        size=(size or "").strip() or None,
        thickness=(thickness or "").strip() or None,
        color=(color or "").strip() or None,
        unit=unit,
        stock=0,
        min_stock=float(min_stock or 0),
        notes=(notes or "").strip() or None,
        active=True,
    )
    db.add(material)
    db.flush()

    if initial > 0:
        adjust_stock(
            db,
            material,
            quantity=initial,
            movement_type="entrada",
            reason="Stock inicial",
            user_id=user_id,
            commit=False,
        )
    db.commit()
    db.refresh(material)
    return material


def adjust_stock(
    db: Session,
    material: RawMaterial,
    *,
    quantity: float,
    movement_type: str,
    reason: str = "",
    production_order_id: int | None = None,
    user_id: int | None = None,
    commit: bool = True,
) -> RawMaterial:
    qty = float(quantity or 0)
    if qty <= 0:
        raise ValueError("La cantidad debe ser mayor a cero.")
    if movement_type not in ("entrada", "salida"):
        raise ValueError("Tipo de movimiento inválido.")

    previous = float(material.stock or 0)
    if movement_type == "salida":
        new_stock = previous - qty
        if new_stock < -0.0001:
            raise ValueError(
                f"Stock insuficiente de {material.label}. "
                f"Disponible: {previous:g} {material.unit}, solicitado: {qty:g}."
            )
        signed = -qty
    else:
        new_stock = previous + qty
        signed = qty

    material.stock = round(new_stock, 3)
    _add_movement(
        db,
        material,
        movement_type=movement_type,
        quantity=signed,
        reason=reason or ("Reabastecimiento" if movement_type == "entrada" else "Consumo"),
        production_order_id=production_order_id,
        user_id=user_id,
        previous_stock=previous,
        new_stock=material.stock,
    )
    if commit:
        db.commit()
        db.refresh(material)
    else:
        db.flush()

    min_stock = float(material.min_stock or 0)
    new_stock = float(material.stock or 0)
    if previous > min_stock and new_stock <= min_stock:
        try:
            from app.services.notification_service import NotificationService

            NotificationService.notify_material_shortage(
                material=getattr(material, "label", None) or material.name,
                stock=new_stock,
                min_stock=min_stock,
                material_id=material.id,
            )
        except Exception:
            pass
    return material


def _add_movement(
    db: Session,
    material: RawMaterial,
    *,
    movement_type: str,
    quantity: float,
    reason: str,
    user_id: int | None = None,
    production_order_id: int | None = None,
    previous_stock: float | None = None,
    new_stock: float | None = None,
) -> RawMaterialMovement:
    prev = previous_stock if previous_stock is not None else float(material.stock or 0)
    new = new_stock if new_stock is not None else float(material.stock or 0)
    mov = RawMaterialMovement(
        raw_material_id=material.id,
        movement_type=movement_type,
        quantity=quantity,
        previous_stock=prev,
        new_stock=new,
        reason=reason,
        production_order_id=production_order_id,
        created_by=user_id,
    )
    db.add(mov)
    return mov


def parse_raw_material_qty(value) -> float | None:
    """Normaliza cantidad desde formulario ('0,5' / '0.5'). Vacío → None."""
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        qty = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Cantidad inválida. Use números decimales, por ejemplo 0.25 o 0.5."
        ) from exc
    if qty <= 0:
        raise ValueError("La cantidad a consumir debe ser mayor a cero (ej. 0.25, 0.5, 1).")
    return round(qty, 3)


def _clean_raw_material_row(row: dict | None) -> dict:
    data = row if isinstance(row, dict) else {}
    rm_id = data.get("raw_material_id")
    try:
        parsed_id = int(rm_id) if rm_id is not None and str(rm_id).strip().isdigit() else None
    except (TypeError, ValueError):
        parsed_id = None
    qty = data.get("qty")
    try:
        parsed_qty = round(float(qty), 3) if qty is not None and str(qty).strip() != "" else None
    except (TypeError, ValueError):
        parsed_qty = None
    return {
        "raw_material_id": parsed_id,
        "qty": parsed_qty,
        "label": str(data.get("label") or "").strip(),
        "unit": str(data.get("unit") or "").strip(),
    }


def normalize_raw_material_items(items: list[dict] | None) -> list[dict]:
    cleaned: list[dict] = []
    for row in items or []:
        spec = _clean_raw_material_row(row)
        if spec["raw_material_id"] and spec["qty"]:
            cleaned.append(spec)
    return cleaned


def parse_fabrication_raw_materials(order: ProductionOrder) -> list[dict]:
    if order.fabrication_raw_materials:
        try:
            raw = json.loads(order.fabrication_raw_materials)
            if isinstance(raw, list):
                return normalize_raw_material_items(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    if order.raw_material_id and order.raw_material_qty:
        return normalize_raw_material_items(
            [{"raw_material_id": order.raw_material_id, "qty": order.raw_material_qty}]
        )
    return []


def serialize_fabrication_raw_materials(items: list[dict] | None) -> str | None:
    cleaned = normalize_raw_material_items(items)
    if not cleaned:
        return None
    return json.dumps(cleaned, ensure_ascii=False)


def parse_raw_material_items_from_form(form) -> list[dict]:
    ids = form.getlist("raw_material_id")
    qtys = form.getlist("raw_material_qty")
    items: list[dict] = []
    for index, rm_id in enumerate(ids):
        qty_raw = qtys[index] if index < len(qtys) else ""
        id_text = str(rm_id or "").strip()
        qty_text = str(qty_raw or "").strip()
        if id_text or qty_text:
            parsed_qty = parse_raw_material_qty(qty_raw) if qty_text else None
            parsed_id = int(id_text) if id_text.isdigit() else None
            items.append({"raw_material_id": parsed_id, "qty": parsed_qty})
    return items


def sync_legacy_raw_material_fields(order: ProductionOrder, items: list[dict]) -> None:
    cleaned = normalize_raw_material_items(items)
    order.fabrication_raw_materials = serialize_fabrication_raw_materials(cleaned)
    if cleaned:
        order.raw_material_id = cleaned[0]["raw_material_id"]
        order.raw_material_qty = cleaned[0]["qty"]
    else:
        order.raw_material_id = None
        order.raw_material_qty = None


def set_fabrication_source(
    db: Session,
    order: ProductionOrder,
    *,
    use_fabrication_materials: bool,
    raw_material_id: int | None = None,
    raw_material_qty: float | None = None,
    raw_material_items: list[dict] | None = None,
) -> ProductionOrder:
    order.use_fabrication_materials = bool(use_fabrication_materials)
    if not use_fabrication_materials:
        order.raw_material_id = None
        order.raw_material_qty = None
        order.fabrication_raw_materials = None
        db.flush()
        return order

    if raw_material_items is not None:
        pending = raw_material_items
    elif raw_material_id:
        pending = [{"raw_material_id": raw_material_id, "qty": raw_material_qty}]
    else:
        pending = []

    if not pending:
        raise ValueError("Seleccione al menos una materia prima a utilizar.")

    stored: list[dict] = []
    for index, row in enumerate(pending, start=1):
        rm_id = row.get("raw_material_id")
        if not rm_id:
            raise ValueError(f"Seleccione la materia prima #{index}.")
        material = get_raw_material(db, int(rm_id))
        if not material or not material.active:
            raise ValueError(f"La materia prima #{index} no existe o está inactiva.")

        qty_raw = row.get("qty")
        if qty_raw is None:
            raise ValueError(
                f"Indique cuántas planchas o metros consumirá en la fila #{index}. "
                "Puede usar fracciones: 0.25, 0.5, 0.75, 1…"
            )
        qty = round(float(qty_raw), 3)
        if qty <= 0:
            raise ValueError(f"La cantidad de la fila #{index} debe ser mayor a cero.")

        if float(material.stock or 0) < qty:
            raise ValueError(
                f"Stock insuficiente de {material.label}. "
                f"Disponible: {float(material.stock or 0):g} {material.unit}, solicitado: {qty:g}."
            )
        stored.append(
            {
                "raw_material_id": material.id,
                "qty": qty,
                "label": material.label,
                "unit": material.unit,
            }
        )

    sync_legacy_raw_material_fields(order, stored)
    db.flush()
    return order


def consume_for_production(
    db: Session,
    order: ProductionOrder,
    *,
    user_id: int | None = None,
) -> None:
    """Descuenta materia prima al pasar la OP a producción."""
    if not order.use_fabrication_materials:
        return

    items = parse_fabrication_raw_materials(order)
    if not items:
        raise ValueError("La orden usa material de fabricación pero no tiene materia prima asignada.")

    for row in items:
        material = get_raw_material(db, row["raw_material_id"])
        if not material:
            raise ValueError("Materia prima no encontrada.")
        qty = float(row["qty"] or 0)
        if qty <= 0:
            raise ValueError("Indique la cantidad de materia prima a consumir.")
        adjust_stock(
            db,
            material,
            quantity=qty,
            movement_type="salida",
            reason=f"OP-{order.id:04d} → Producción",
            production_order_id=order.id,
            user_id=user_id,
            commit=False,
        )


def material_to_dict(material: RawMaterial) -> dict:
    return {
        "id": material.id,
        "kind": material.kind,
        "material_type": material.material_type,
        "name": material.name,
        "size": material.size or "",
        "thickness": material.thickness or "",
        "color": material.color or "",
        "unit": material.unit,
        "stock": float(material.stock or 0),
        "min_stock": float(material.min_stock or 0),
        "is_low_stock": material.is_low_stock,
        "label": material.label,
        "active": bool(material.active),
    }
