from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship

from app.database import Base


class QuotationItem(Base):

    __tablename__ = "quotation_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # RELACIÓN COTIZACIÓN
    quotation_id = Column(
        Integer,
        ForeignKey("quotations.id")
    )

    # RELACIÓN PRODUCTO
    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=True
    )

    # CANTIDAD
    quantity = Column(Integer)

    # DETALLE PRODUCTO
    detail = Column(String)

    # PERSONALIZADOS
    measure = Column(String)

    shape = Column(String)

    color = Column(String)

    logo = Column(String)

    # PRECIOS
    unit_price = Column(Float)

    total = Column(Float)

    # RELACIÓN PRODUCTO
    product = relationship(
        "Product"
    )