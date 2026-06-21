from sqlalchemy import Boolean, Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship

from app.database import Base


class QuotationItem(Base):

    __tablename__ = "quotation_items"
    id = Column(Integer, primary_key=True, index=True)
    # RELACIÓN COTIZACIÓN
    quotation_id = Column(Integer, ForeignKey("quotations.id"))
    # RELACIÓN PRODUCTO
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    # CANTIDAD
    quantity = Column(Integer)
    # DETALLE PRODUCTO
    detail = Column(String)
    # PERSONALIZADOS
    measure = Column(String)
    theme = Column(String)
    color = Column(String)
    logo = Column(Boolean, default=False)
    logo_type = Column(String(20), default="sin_logo", nullable=False)
    item_discount = Column(Float, default=0, nullable=False)
    # PRECIOS
    unit_price = Column(Float)
    total = Column(Float)
    product_image = Column(String, nullable=True)
    # RELACIÓN PRODUCTO
    product = relationship("Product")
    quotation = relationship(
    "Quotation",
    back_populates="items"
    )
    design_tracking = relationship(
        "DesignTracking",
        back_populates="quotation_item",
        uselist=False,
        cascade="all, delete-orphan",
    )