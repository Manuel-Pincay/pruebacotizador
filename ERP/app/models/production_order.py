from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), unique=True, index=True)

    delivery_date = Column(DateTime)
    priority = Column(String, default="media")
    designer = Column(String)
    fabricator = Column(String)
    assigned_to = Column(String)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    status = Column(String(50), default="pendiente")

    observations = Column(String)
    notes = Column(String)

    design_file_name = Column(String(255))
    design_material = Column(String(50))
    design_size = Column(String(100))
    design_usb_reference = Column(String(100))
    design_notes = Column(Text)
    design_copies = Column(Integer, default=1)
    design_completed_at = Column(DateTime)
    design_completed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    quotation = relationship("Quotation", back_populates="production_order")
    assignee = relationship("User", foreign_keys=[assigned_to_user_id])
    design_completer = relationship("User", foreign_keys=[design_completed_by])
    history = relationship(
        "ProductionOrderHistory",
        back_populates="production_order",
        order_by="ProductionOrderHistory.created_at",
        cascade="all, delete-orphan",
    )
