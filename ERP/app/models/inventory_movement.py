from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey

from datetime import datetime

from app.database import Base


class InventoryMovement(Base):

    __tablename__ = "inventory_movements"

    id = Column(
        Integer,
        primary_key=True
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id")
    )

    movement_type = Column(String)

    quantity = Column(Integer)

    previous_stock = Column(Integer)

    new_stock = Column(Integer)

    reason = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )