from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DesignTracking(Base):
    __tablename__ = "design_tracking"

    id = Column(Integer, primary_key=True)
    quotation_item_id = Column(
        Integer,
        ForeignKey("quotation_items.id"),
        unique=True,
        nullable=False,
    )
    status = Column(String(50), default="pendiente_diseno")
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_to = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    quotation_item = relationship(
        "QuotationItem",
        back_populates="design_tracking",
        uselist=False,
    )
    assigned_user = relationship("User", foreign_keys=[assigned_to_user_id])
    observations = relationship(
        "DesignObservation",
        back_populates="design_tracking",
        cascade="all, delete-orphan",
        order_by="DesignObservation.created_at.desc()",
    )
