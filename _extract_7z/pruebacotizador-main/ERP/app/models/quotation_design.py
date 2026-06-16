from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class QuotationDesign(Base):

    __tablename__ = "quotation_designs"

    id = Column(Integer, primary_key=True)

    quotation_id = Column(
        Integer,
        ForeignKey("quotations.id"),
        nullable=False,
    )

    filename = Column(String(255), nullable=False)

    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    quotation = relationship("Quotation", back_populates="designs")
