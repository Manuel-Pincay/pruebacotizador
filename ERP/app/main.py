from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import SessionLocal
from app.utils.cached_static import CachedStaticFiles

from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.production_order import ProductionOrder
from app.models.inventory_movement import InventoryMovement
from app.models.shipment import Shipment
from app.models.company_config import CompanyConfig
from app.models.activity_log import ActivityLog

from app.services.user_bootstrap import ensure_admin_user

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

@app.on_event("startup")
def bootstrap_admin():
    db = SessionLocal()
    try:
        user, created = ensure_admin_user(db)
        if created:
            print("ADMIN CREADO")
    finally:
        db.close()


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
