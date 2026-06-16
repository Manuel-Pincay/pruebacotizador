from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class QuotationPayment(Base):

    __tablename__ = "quotation_payments"

    id = Column(Integer, primary_key=True)

    quotation_id = Column(
        Integer,
        ForeignKey("quotations.id"),
        nullable=False,
    )

    amount = Column(Numeric(12, 2), nullable=False)

    payment_date = Column(DateTime, nullable=False)

    payment_method = Column(String(50))

    reference = Column(String(100))

    notes = Column(Text)

    transfer_receipt = Column(String(255))

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    quotation = relationship(
        "Quotation",
        back_populates="payments",
    )
