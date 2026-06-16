from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ProductionOrderHistory(Base):
    __tablename__ = "production_order_history"

    id = Column(Integer, primary_key=True)
    production_order_id = Column(
        Integer,
        ForeignKey("production_orders.id"),
        nullable=False,
        index=True,
    )
    status = Column(String(50), nullable=False)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    production_order = relationship("ProductionOrder", back_populates="history")
    author = relationship("User", foreign_keys=[created_by])
