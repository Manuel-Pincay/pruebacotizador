from datetime import datetime

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import DateTime

from sqlalchemy.orm import relationship

from app.database import Base


class InventoryMovement(Base):

    __tablename__ = "inventory_movements"

    id = Column(
        Integer,
        primary_key=True
    )

    # PRODUCTO RELACIONADO
    product_id = Column(
        Integer,
        ForeignKey("products.id")
    )

    # entrada / salida
    movement_type = Column(String)

    # cantidad movimiento
    quantity = Column(Float)

    # stock antes
    previous_stock = Column(Float)

    # stock después
    new_stock = Column(Float)

    # motivo
    reason = Column(String)

    # fecha
    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    # RELACIÓN PRODUCTO
    product = relationship(
        "Product"
    )