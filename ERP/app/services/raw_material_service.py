"""Inventario de materia prima (planchas / vinil) y consumo en producción."""

from __future__ import annotations

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


def set_fabrication_source(
    db: Session,
    order: ProductionOrder,
    *,
    use_fabrication_materials: bool,
    raw_material_id: int | None = None,
    raw_material_qty: float | None = None,
) -> ProductionOrder:
    order.use_fabrication_materials = bool(use_fabrication_materials)
    if not use_fabrication_materials:
        order.raw_material_id = None
        order.raw_material_qty = None
        db.flush()
        return order

    if not raw_material_id:
        raise ValueError("Seleccione la materia prima a utilizar.")
    material = get_raw_material(db, int(raw_material_id))
    if not material or not material.active:
        raise ValueError("La materia prima seleccionada no existe o está inactiva.")

    qty = float(raw_material_qty or 0)
    if qty <= 0:
        # Por defecto: 1 plancha o metros = copias (heurística mínima)
        copies = max(1, int(order.design_copies or 1))
        qty = float(copies) if material.kind == "plancha" else float(copies)

    if float(material.stock or 0) < qty:
        raise ValueError(
            f"Stock insuficiente de {material.label}. "
            f"Disponible: {float(material.stock or 0):g} {material.unit}, solicitado: {qty:g}."
        )

    order.raw_material_id = material.id
    order.raw_material_qty = qty
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
    if not order.raw_material_id:
        raise ValueError("La orden usa material de fabricación pero no tiene materia prima asignada.")

    material = get_raw_material(db, order.raw_material_id)
    if not material:
        raise ValueError("Materia prima no encontrada.")

    qty = float(order.raw_material_qty or 0)
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
