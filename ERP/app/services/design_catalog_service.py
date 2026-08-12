"""Catálogos de medida y USB para diseño/fabricación."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.productsize import ProductSize
from app.models.usb_reference import UsbReference
from app.services.production_order_service import DESIGN_SIZES, USB_REFERENCES


DEFAULT_SIZES = list(DESIGN_SIZES)
DEFAULT_USBS = list(USB_REFERENCES)


def ensure_design_catalogs(db: Session) -> None:
    """Si están vacíos, carga valores base (idempotente)."""
    if db.query(ProductSize).count() == 0:
        for name in DEFAULT_SIZES:
            db.add(ProductSize(name=name))
        db.flush()
    if db.query(UsbReference).count() == 0:
        for name in DEFAULT_USBS:
            db.add(UsbReference(name=name))
        db.flush()


def list_design_sizes(db: Session) -> list[ProductSize]:
    ensure_design_catalogs(db)
    return db.query(ProductSize).order_by(ProductSize.name.asc()).all()


def list_usb_references(db: Session) -> list[UsbReference]:
    ensure_design_catalogs(db)
    return db.query(UsbReference).order_by(UsbReference.name.asc()).all()
