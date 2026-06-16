from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ProductionTracking(Base):

    __tablename__ = "production_tracking"

    id = Column(Integer, primary_key=True)

    quotation_id = Column(
        Integer,
        ForeignKey("quotations.id"),
        unique=True,
        nullable=True,
    )

    quotation_item_id = Column(
        Integer,
        ForeignKey("quotation_items.id"),
        nullable=True,
        unique=True,
    )

    status = Column(String(50), default="pendiente")

    assigned_to = Column(String(255))

    started_at = Column(DateTime)

    completed_at = Column(DateTime)

    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    quotation = relationship(
        "Quotation",
        back_populates="production_tracking",
        uselist=False,
    )

    quotation_item = relationship(
        "QuotationItem",
        backref="production_tracking",
        uselist=False,
    )
