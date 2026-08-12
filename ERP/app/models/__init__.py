"""Registra todos los modelos en metadata (Alembic / migraciones)."""

from app.models.activity_log import ActivityLog
from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.models.electronic_invoice_line import ElectronicInvoiceLine
from app.models.inventory_movement import InventoryMovement
from app.models.measurementunit import MeasurementUnit
from app.models.raw_material import RawMaterial
from app.models.raw_material_movement import RawMaterialMovement
from app.models.product import Product
from app.models.productcategory import ProductCategory
from app.models.productcolor import ProductColor
from app.models.productmaterial import ProductMaterial
from app.models.producttheme import ProductTheme
from app.models.productthickness import ProductThickness
from app.models.productsize import ProductSize
from app.models.usb_reference import UsbReference
from app.models.design_observation import DesignObservation
from app.models.design_tracking import DesignTracking
from app.models.production_order import ProductionOrder
from app.models.production_order_history import ProductionOrderHistory
from app.models.production_tracking import ProductionTracking
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.quotation_payment import QuotationPayment
from app.models.quotation_design import QuotationDesign
from app.models.quotation_event import QuotationEvent
from app.models.notification import Notification
from app.models.shipment import Shipment
from app.models.sri_certificate import SriCertificate
from app.models.sri_emission_point import SriEmissionPoint
from app.models.sri_establishment import SriEstablishment
from app.models.sri_sequence import SriSequence
from app.models.user import User

__all__ = [
    "ActivityLog",
    "Client",
    "CompanyConfig",
    "ElectronicInvoice",
    "ElectronicInvoiceLine",
    "InventoryMovement",
    "MeasurementUnit",
    "RawMaterial",
    "RawMaterialMovement",
    "Product",
    "ProductCategory",
    "ProductColor",
    "ProductMaterial",
    "ProductTheme",
    "ProductThickness",
    "ProductSize",
    "UsbReference",
    "DesignObservation",
    "DesignTracking",
    "ProductionOrder",
    "ProductionOrderHistory",
    "ProductionTracking",
    "Quotation",
    "QuotationItem",
    "QuotationPayment",
    "QuotationDesign",
    "QuotationEvent",
    "Notification",
    "Shipment",
    "SriCertificate",
    "SriEmissionPoint",
    "SriEstablishment",
    "SriSequence",
    "User",
]
