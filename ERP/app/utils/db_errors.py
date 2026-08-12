"""Mensajes amigables para errores de integridad de BD (FK, unique, etc.)."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError


def integrity_error_user_message(exc: IntegrityError | Exception) -> str:
    """Traduce IntegrityError de MySQL/SQLAlchemy a texto usable en UI."""
    raw = str(getattr(exc, "orig", None) or exc).lower()

    if "1451" in raw or "foreign key constraint fails" in raw:
        if "quotation_items" in raw:
            return (
                "No se puede eliminar porque está usado en una o más cotizaciones. "
                "Puede editarlo o dejarlo inactivo; no borre el catálogo si ya se cotizó."
            )
        if "electronic_invoice" in raw:
            return (
                "No se puede eliminar porque está referenciado en facturas electrónicas."
            )
        if "inventory_movement" in raw or "inventory_movements" in raw:
            return (
                "No se puede eliminar porque tiene movimientos de inventario asociados."
            )
        if "quotations" in raw and "client" in raw:
            return (
                "No se puede eliminar el cliente porque tiene cotizaciones asociadas."
            )
        return (
            "No se puede eliminar este registro porque está en uso en otra parte del sistema."
        )

    if "1062" in raw or "duplicate" in raw or "unique" in raw:
        return "Ya existe un registro con esos datos (código o valor duplicado)."

    if "1452" in raw:
        return "Referencia inválida: el registro relacionado no existe."

    return "La operación no se pudo completar por una restricción de la base de datos."


def is_integrity_error(exc: Exception) -> bool:
    if isinstance(exc, IntegrityError):
        return True
    text = str(getattr(exc, "orig", None) or exc).lower()
    return "integrityerror" in text or "1451" in text or "1062" in text
