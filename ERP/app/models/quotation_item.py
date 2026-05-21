from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import ForeignKey

from app.database import Base

class QuotationItem(Base):

    __tablename__ = "quotation_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    quotation_id = Column(
        Integer,
        ForeignKey("quotations.id")
    )

    quantity = Column(Integer)

    detail = Column(String)

    measure = Column(String)

    shape = Column(String)

    color = Column(String)

    logo = Column(String)

    unit_price = Column(Float)

    total = Column(Float)