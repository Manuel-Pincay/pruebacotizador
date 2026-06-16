from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from datetime import datetime

from app.database import Base


class Shipment(Base):

    __tablename__ = "shipments"

    id = Column(
        Integer,
        primary_key=True
    )

    quotation_id = Column(
        Integer,
        ForeignKey("quotations.id")
    )

    guide_number = Column(String)

    customer_name = Column(String)

    customer_phone = Column(String)

    origin_city = Column(
        String,
        default="Manta"
    )

    destination_city = Column(String)

    destination_address = Column(String)

    carrier = Column(String)

    boxes = Column(Integer)

    notes = Column(String)

    customer_id_number = Column(String)

    status = Column(
        String,
        default="pendiente"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    quotation = relationship("Quotation", back_populates="shipments")