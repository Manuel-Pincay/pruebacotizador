"""Registra todos los modelos en metadata (Alembic / migraciones)."""

from app.models.activity_log import ActivityLog
from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.models.inventory_movement import InventoryMovement
from app.models.measurementunit import MeasurementUnit
from app.models.product import Product
from app.models.productcategory import ProductCategory
from app.models.productcolor import ProductColor
from app.models.productmaterial import ProductMaterial
from app.models.producttheme import ProductTheme
from app.models.productthickness import ProductThickness
from app.models.production_order import ProductionOrder
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.shipment import Shipment
from app.models.user import User

__all__ = [
    "ActivityLog",
    "Client",
    "CompanyConfig",
    "InventoryMovement",
    "MeasurementUnit",
    "Product",
    "ProductCategory",
    "ProductColor",
    "ProductMaterial",
    "ProductTheme",
    "ProductThickness",
    "ProductionOrder",
    "Quotation",
    "QuotationItem",
    "Shipment",
    "User",
]
