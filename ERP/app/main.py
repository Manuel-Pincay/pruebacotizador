from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import socket

from app.database import Base, engine, SessionLocal

from app.models.user import User
from app.models.quotation import Quotation
from app.models.quotation_item import QuotationItem
from app.models.production_order import ProductionOrder
from app.models.inventory_movement import InventoryMovement
from app.models.shipment import Shipment

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

Base.metadata.create_all(bind=engine)

app = FastAPI(title="INNOVA ARTE ERP")

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