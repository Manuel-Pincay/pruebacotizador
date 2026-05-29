from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import socket
from fastapi.templating import Jinja2Templates
from app.database import Base, engine, SessionLocal
from app.database import SessionLocal

from app.models.user import User
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.production_order import ProductionOrder
from app.models.inventory_movement import InventoryMovement
from app.models.shipment import Shipment
from app.models.company_config import CompanyConfig


from app.auth.security import hash_password

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

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SISTEMA ERP")
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(
    directory="app/templates"
)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)



app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
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


def inject_global_config():

    db = SessionLocal()

    try:

        config = db.query(
            CompanyConfig
        ).first()

        return {
            "config": config
        }

    finally:

        db.close()

# Note: template globals are registered per-router in their modules to avoid
# importing DB models at module import time.