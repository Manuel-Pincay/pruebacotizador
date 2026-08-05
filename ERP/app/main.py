from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine, SessionLocal
from app.utils.cached_static import CachedStaticFiles

from app.models.user import User
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.quotation_payment import QuotationPayment
from app.models.quotation_design import QuotationDesign
from app.models.quotation_event import QuotationEvent
from app.models.notification import Notification
from app.models.design_tracking import DesignTracking
from app.models.production_order import ProductionOrder
from app.models.production_order_history import ProductionOrderHistory
from app.models.design_observation import DesignObservation
from app.models.production_tracking import ProductionTracking
from app.models.inventory_movement import InventoryMovement
from app.models.raw_material import RawMaterial
from app.models.raw_material_movement import RawMaterialMovement
from app.models.shipment import Shipment
from app.models.company_config import CompanyConfig
from app.models.activity_log import ActivityLog
from app.models.client import Client
from app.models.product import Product

from app.auth.security import hash_password

from app.db_bootstrap import prepare_database

from app.routes import auth
from app.routes import dashboard
from app.routes import clients
from app.routes import products
from app.routes import quotations
from app.routes import payments
from app.routes import production
from app.routes import production_condensed
from app.routes import fabrication_condensed
from app.routes import design
from app.routes import inventory
from app.routes import shipments
from app.routes import users
from app.routes import config
from app.routes import imports
from app.routes import product_settings
from app.routes import billing
from app.routes import reports
from app.routes import notifications

from app.config.settings import settings
from app.error_handlers import register_error_handlers

try:
    prepare_database()
    settings.validate_security_settings()
    table_count = len(Base.metadata.tables)
    print(f"\n✓ Base de datos MySQL lista ({table_count} tablas)\n")
except RuntimeError as e:
    print("\n" + "=" * 60)
    print("ERROR DE SEGURIDAD EN PRODUCCIÓN")
    print("=" * 60)
    print(str(e))
    raise
except Exception as e:
    print("\n" + "=" * 60)
    print("ERROR PREPARANDO BASE DE DATOS")
    print("=" * 60)
    print(type(e).__name__)
    print(str(e))
    raise


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        from app.services.notification_service import NotificationService
        from app.services.telegram_service import reset_telegram_service

        reset_telegram_service()
        NotificationService.notify_server_started()
    except Exception:
        pass
    yield


app = FastAPI(title="SISTEMA ERP", lifespan=lifespan)
register_error_handlers(app)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)

app.mount(
    "/uploads",
    CachedStaticFiles(directory="uploads"),
    name="uploads"
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(clients.router)
app.include_router(products.router)
app.include_router(quotations.router)
app.include_router(payments.router)
app.include_router(production_condensed.router)
app.include_router(fabrication_condensed.router)
app.include_router(design.router)
app.include_router(production.router)
app.include_router(inventory.router)
app.include_router(shipments.router)
app.include_router(users.router)
app.include_router(config.router)
app.include_router(imports.router)
app.include_router(
    product_settings.router
)
app.include_router(billing.router)
app.include_router(reports.router)
app.include_router(notifications.router)


def create_admin():

    db = SessionLocal()

    user = db.query(User).filter(
        User.username == "admin"
    ).first()

    if not user:

        admin = User(
            username="admin",
            full_name="Administrador",
            password=hash_password("123456"),
            role="admin"
        )

        db.add(admin)
        db.commit()

        print("ADMIN CREADO")

    db.close()


def _seed_admin_telegram_from_env() -> None:
    """Si el admin aún no tiene Chat ID, copia el del .env (una sola vez)."""
    try:
        from app.services.telegram_service import parse_chat_ids

        ids = parse_chat_ids(settings.telegram_chat_id)
        if not ids:
            return
        db = SessionLocal()
        try:
            admin = (
                db.query(User)
                .filter(User.username == "admin", User.role == "admin")
                .first()
            )
            if admin and not (admin.telegram_chat_id or "").strip():
                admin.telegram_chat_id = ids[0]
                admin.telegram_notify = True
                db.commit()
        finally:
            db.close()
    except Exception:
        pass


create_admin()
_seed_admin_telegram_from_env()
