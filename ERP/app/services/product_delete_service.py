"""Archivar / reactivar / borrar productos del catálogo."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.electronic_invoice_line import ElectronicInvoiceLine
from app.models.inventory_movement import InventoryMovement
from app.models.product import Product
from app.models.quotation_item import QuotationItem
from app.services.transport_product_service import TRANSPORT_PRODUCT_CODE


def product_is_referenced(db: Session, product_id: int) -> bool:
    if (
        db.query(QuotationItem.id)
        .filter(QuotationItem.product_id == product_id)
        .limit(1)
        .first()
    ):
        return True
    if (
        db.query(InventoryMovement.id)
        .filter(InventoryMovement.product_id == product_id)
        .limit(1)
        .first()
    ):
        return True
    if (
        db.query(ElectronicInvoiceLine.id)
        .filter(ElectronicInvoiceLine.product_id == product_id)
        .limit(1)
        .first()
    ):
        return True
    return False


def product_delete_block_reason(db: Session, product_id: int) -> str | None:
    """Motivo por el que no se puede borrar físicamente (sí se puede archivar)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if product and (product.code or "").strip().upper() == TRANSPORT_PRODUCT_CODE:
        return "El servicio de transporte es del sistema y no se puede eliminar."

    if (
        db.query(QuotationItem.id)
        .filter(QuotationItem.product_id == product_id)
        .limit(1)
        .first()
    ):
        return (
            "Este producto está en cotizaciones. No se puede eliminar; "
            "archívelo para ocultarlo del catálogo sin romper el historial."
        )

    if (
        db.query(InventoryMovement.id)
        .filter(InventoryMovement.product_id == product_id)
        .limit(1)
        .first()
    ):
        return (
            "Este producto tiene movimientos de inventario. "
            "Archívelo en lugar de eliminarlo."
        )

    if (
        db.query(ElectronicInvoiceLine.id)
        .filter(ElectronicInvoiceLine.product_id == product_id)
        .limit(1)
        .first()
    ):
        return (
            "Este producto aparece en facturas electrónicas. "
            "Archívelo en lugar de eliminarlo."
        )

    return None


def archive_product(db: Session, product: Product) -> Product:
    if (product.code or "").strip().upper() == TRANSPORT_PRODUCT_CODE:
        raise ValueError("El servicio de transporte no se puede archivar.")
    product.active = False
    db.flush()
    return product


def reactivate_product(db: Session, product: Product) -> Product:
    product.active = True
    db.flush()
    return product


def safe_delete_product(db: Session, product: Product) -> None:
    """Elimina físicamente solo si no hay referencias; si no, ValueError."""
    reason = product_delete_block_reason(db, product.id)
    if reason:
        raise ValueError(reason)
    db.delete(product)
    db.flush()


def active_products_query(db: Session):
    """Query base de productos disponibles para nuevas operaciones."""
    return db.query(Product).filter(Product.active.is_(True))
