from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class RawMaterialMovement(Base):
    __tablename__ = "raw_material_movements"

    id = Column(Integer, primary_key=True)
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=False, index=True)
    # entrada | salida
    movement_type = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    previous_stock = Column(Float, nullable=False)
    new_stock = Column(Float, nullable=False)
    reason = Column(String(300), nullable=True)
    production_order_id = Column(Integer, ForeignKey("production_orders.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    raw_material = relationship("RawMaterial", back_populates="movements")
    production_order = relationship("ProductionOrder")
    creator = relationship("User")
