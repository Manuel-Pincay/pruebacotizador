from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine, SessionLocal
from app.utils.cached_static import CachedStaticFiles

from app.models.user import User
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.production_order import ProductionOrder
from app.models.inventory_movement import InventoryMovement
from app.models.shipment import Shipment
from app.models.company_config import CompanyConfig
from app.models.activity_log import ActivityLog
from app.models.client import Client
from app.models.product import Product

from app.auth.security import hash_password

from app.db_migrations import run_sqlite_migrations

from app.routes import auth
from app.routes import dashboard
from app.routes import clients
from app.routes import products
from app.routes import quotations
from app.routes import production
from app.routes import inventory
from app.routes import shipments
from app.routes import users
from app.routes import config
from app.routes import imports
from app.routes import product_settings

from app.config.settings import settings
print("\n========== MODELOS ==========")

for table in Base.metadata.tables:
    print(f"✓ {table}")

print("=============================\n")

try:

    print("Creando tablas MySQL...")

    Base.metadata.create_all(bind=engine)

    print("✓ Tablas creadas correctamente")

except Exception as e:

    print("\n" + "=" * 80)
    print("ERROR CREANDO TABLAS")
    print("=" * 80)

    print(type(e).__name__)
    print(str(e))

    raise
if settings.is_sqlite:
    run_sqlite_migrations()

app = FastAPI(title="SISTEMA ERP")

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
app.include_router(production.router)
app.include_router(inventory.router)
app.include_router(shipments.router)
app.include_router(users.router)
app.include_router(config.router)
app.include_router(imports.router)
app.include_router(
    product_settings.router
)


print("Creando tablas...")
Base.metadata.create_all(bind=engine)
print("Tablas verificadas")

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



create_admin()