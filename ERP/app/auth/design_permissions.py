"""Permisos del módulo de diseño (admin vs diseñador)."""

from __future__ import annotations

from app.auth.permissions import ROLE_ADMIN, ROLE_DISENADOR
from app.models.production_order import ProductionOrder
from app.models.quotation_item import QuotationItem
from app.models.user import User


def is_design_admin(user: User) -> bool:
    return user.role == ROLE_ADMIN


def is_designer(user: User) -> bool:
    return user.role == ROLE_DISENADOR


def can_access_design_module(user: User) -> bool:
    return user.role in {ROLE_ADMIN, ROLE_DISENADOR}


def can_view_design_item(user: User, item: QuotationItem) -> bool:
    if is_design_admin(user):
        return True
    if not is_designer(user):
        return False
    quotation = item.quotation
    if quotation and quotation.production_order:
        order = quotation.production_order
        if order.assigned_to_user_id is None:
            return True
        return order.assigned_to_user_id == user.id
    tracking = item.design_tracking
    if not tracking or not tracking.assigned_to_user_id:
        return True
    return tracking.assigned_to_user_id == user.id


def can_view_design_order(user: User, order: ProductionOrder) -> bool:
    if is_design_admin(user):
        return True
    if not is_designer(user):
        return False
    if order.assigned_to_user_id is None:
        return True
    return order.assigned_to_user_id == user.id


def can_edit_design_order(user: User, order: ProductionOrder) -> bool:
    if is_design_admin(user):
        return True
    if not is_designer(user):
        return False
    if order.assigned_to_user_id is None:
        return True
    return order.assigned_to_user_id == user.id


def can_delete_design_order(user: User) -> bool:
    return is_design_admin(user)


def can_reassign_design_order(user: User) -> bool:
    return is_design_admin(user)


def can_export_design_orders(user: User) -> bool:
    return is_design_admin(user)


def designer_item_scope_user_id(user: User) -> int | None:
    """None = sin filtro (admin ve todo)."""
    if is_designer(user):
        return user.id
    return None
