from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Date

from sqlalchemy.orm import relationship

from datetime import datetime

from app.database import Base


class ProductionOrder(Base):

    __tablename__ = "production_orders"

    id = Column(
        Integer,
        primary_key=True
    )

    quotation_id = Column(
        Integer,
        ForeignKey("quotations.id")
    )

    delivery_date = Column(Date)

    priority = Column(
        String,
        default="media"
    )

    designer = Column(String)

    fabricator = Column(String)

    priority = Column(String)

    status = Column(String)

    observations = Column(String)

    delivery_date = Column(DateTime)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    quotation = relationship("Quotation")