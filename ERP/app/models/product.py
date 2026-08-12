from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import Boolean

from app.database import Base

class Product(Base):

    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    code = Column(String)
    name = Column(String)
    description = Column(String)
    category = Column(String)
    material = Column(String)
    color = Column(String)
    size = Column(String)
    thickness = Column(String)
    price = Column(Float)
    cost = Column(Float)
    theme = Column(String)
    stock = Column(Integer)
    custom = Column(Boolean, default=False, nullable=False)
    # Soft-delete: archivado deja de aparecer en catálogo/nuevas cotizaciones
    # pero las cotizaciones históricas siguen apuntando al producto.
    active = Column(Boolean, default=True, nullable=False)
    image = Column(String)
    codigo_auxiliar = Column(String(50), nullable=True)
    codigo_iva = Column(String(5), default="0")
    tarifa_iva = Column(Float, default=0)