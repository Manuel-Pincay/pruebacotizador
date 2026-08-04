from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class QuotationEvent(Base):
    """Bitácora de acciones sobre una cotización."""

    __tablename__ = "quotation_events"

    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(80), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    quotation = relationship("Quotation", back_populates="events")
    user = relationship("User")
