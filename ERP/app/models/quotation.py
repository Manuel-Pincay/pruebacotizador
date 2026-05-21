from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey

from sqlalchemy.orm import relationship

from datetime import datetime

from app.database import Base


class Quotation(Base):

    __tablename__ = "quotations"

    id = Column(Integer, primary_key=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id")
    )

    subtotal = Column(Float)

    discount = Column(Float)

    iva = Column(Float)

    total = Column(Float)

    status = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    client = relationship("Client")
    items = relationship(
    "QuotationItem"
)