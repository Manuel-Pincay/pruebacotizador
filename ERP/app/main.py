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
from app.routes import store
from app.routes import store_cms

from app.config.settings import settings
from app.error_handlers import register_error_handlers
from app.utils.urls import ERP_LEGACY_ROOTS, ERP_PREFIX
from app.models.store_slide import StoreSlide  # noqa: F401
from app.models.store_home_settings import StoreHomeSettings  # noqa: F401

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


@app.middleware("http")
async def redirect_legacy_erp_paths(request, call_next):
    """Redirige /quotations → /erp/quotations (enlaces y favoritos antiguos)."""
    path = request.url.path
    if path == ERP_PREFIX or path.startswith(ERP_PREFIX + "/"):
        return await call_next(request)
    if path in {"/static", "/uploads"} or path.startswith("/static/") or path.startswith("/uploads/"):
        return await call_next(request)

    first = path.lstrip("/").split("/", 1)[0] if path.strip("/") else ""
    if first in ERP_LEGACY_ROOTS:
        from fastapi.responses import RedirectResponse

        target = ERP_PREFIX + (path if path.startswith("/") else "/" + path)
        if request.url.query:
            target = f"{target}?{request.url.query}"
        # 307 conserva método (POST de formularios legacy)
        return RedirectResponse(url=target, status_code=307)

    return await call_next(request)


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

# Tienda pública en /
app.include_router(store.router)

# ERP bajo /erp (sin menú en la tienda; acceso directo /erp/login)
_erp = ERP_PREFIX
app.include_router(auth.router, prefix=_erp)
app.include_router(dashboard.router, prefix=_erp)
app.include_router(clients.router, prefix=_erp)
app.include_router(products.router, prefix=_erp)
app.include_router(quotations.router, prefix=_erp)
app.include_router(payments.router, prefix=_erp)
app.include_router(production_condensed.router, prefix=_erp)
app.include_router(fabrication_condensed.router, prefix=_erp)
app.include_router(design.router, prefix=_erp)
app.include_router(production.router, prefix=_erp)
app.include_router(inventory.router, prefix=_erp)
app.include_router(shipments.router, prefix=_erp)
app.include_router(users.router, prefix=_erp)
app.include_router(config.router, prefix=_erp)
app.include_router(imports.router, prefix=_erp)
app.include_router(product_settings.router, prefix=_erp)
app.include_router(billing.router, prefix=_erp)
app.include_router(reports.router, prefix=_erp)
app.include_router(notifications.router, prefix=_erp)
app.include_router(store_cms.router, prefix=_erp)


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
