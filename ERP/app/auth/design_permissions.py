"""Permisos del módulo de diseño (admin vs diseñador).

Modo colaborativo: todos los diseñadores ven y pueden trabajar
las mismas órdenes en fase de diseño (varios en una sola orden).
La asignación es solo una referencia de responsable, no un candado.
"""

from __future__ import annotations

from app.auth.permissions import ROLE_ADMIN, ROLE_DISENADOR
from app.models.production_order import ProductionOrder
from app.models.quotation_item import QuotationItem
from app.models.user import User

DESIGN_WORK_STATUSES = {"pendiente", "diseno"}
FABRICATION_EDIT_STATUSES = {"pendiente", "diseno", "produccion", "envio"}


def is_design_admin(user: User) -> bool:
    return user.role == ROLE_ADMIN


def is_designer(user: User) -> bool:
    return user.role == ROLE_DISENADOR


def can_access_design_module(user: User) -> bool:
    return user.role in {ROLE_ADMIN, ROLE_DISENADOR}


def _order_status(order: ProductionOrder | None) -> str:
    if not order:
        return ""
    return (order.status or "").strip().lower()


def can_view_design_item(user: User, item: QuotationItem) -> bool:
    """Cualquier diseñador/admin del módulo ve todos los ítems."""
    return can_access_design_module(user)


def can_view_design_order(user: User, order: ProductionOrder) -> bool:
    """Cualquier diseñador/admin del módulo ve todas las órdenes."""
    return can_access_design_module(user)


def can_edit_design_order(user: User, order: ProductionOrder) -> bool:
    """Admin siempre; diseñadores mientras la orden esté en fase de diseño."""
    if is_design_admin(user):
        return True
    if not is_designer(user):
        return False
    return _order_status(order) in DESIGN_WORK_STATUSES


def can_edit_fabrication_data(user: User, order: ProductionOrder) -> bool:
    """Editar archivos, materiales y datos de fabricación sin cambiar el estado."""
    if not order or not can_view_design_order(user, order):
        return False
    if is_design_admin(user):
        return True
    if user.role == "produccion":
        return _order_status(order) in FABRICATION_EDIT_STATUSES
    if is_designer(user):
        return _order_status(order) in FABRICATION_EDIT_STATUSES
    return False


def can_delete_design_order(user: User) -> bool:
    return is_design_admin(user)


def can_reassign_design_order(user: User) -> bool:
    return is_design_admin(user)


def can_self_assign_design_order(user: User, order: ProductionOrder | None) -> bool:
    """Marcarse responsable (opcional). No bloquea a otros diseñadores."""
    if not is_designer(user) or not order:
        return False
    if order.assigned_to_user_id == user.id:
        return False
    return _order_status(order) in DESIGN_WORK_STATUSES


def can_self_assign_design_item(user: User, item: QuotationItem) -> bool:
    """Marcarse responsable del ítem/orden. No bloquea a otros."""
    if not is_designer(user):
        return False
    quotation = item.quotation
    if quotation and quotation.production_order:
        return can_self_assign_design_order(user, quotation.production_order)
    tracking = item.design_tracking
    if tracking and tracking.assigned_to_user_id == user.id:
        return False
    return True


def can_attach_design_images(user: User, item: QuotationItem) -> bool:
    if not can_view_design_item(user, item):
        return False
    return is_design_admin(user) or is_designer(user)


def can_export_design_orders(user: User) -> bool:
    return is_design_admin(user)


def designer_item_scope_user_id(user: User) -> int | None:
    """Siempre None: cola compartida (todos ven todo)."""
    return None
