from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class RawMaterial(Base):
    """Materia prima de fabricación: planchas (MDF/acrílico) o vinil (metros)."""

    __tablename__ = "raw_materials"

    id = Column(Integer, primary_key=True)
    # plancha | vinil
    kind = Column(String(20), nullable=False, default="plancha", index=True)
    # MDF | Acrílico | Vinil impresión | Vinil color | PVC | etc.
    material_type = Column(String(50), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    size = Column(String(80), nullable=True)
    thickness = Column(String(40), nullable=True)
    color = Column(String(60), nullable=True)
    # planchas | metros
    unit = Column(String(20), nullable=False, default="planchas")
    stock = Column(Float, nullable=False, default=0)
    min_stock = Column(Float, nullable=False, default=0)
    notes = Column(String(300), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    movements = relationship(
        "RawMaterialMovement",
        back_populates="raw_material",
        cascade="all, delete-orphan",
        order_by="RawMaterialMovement.created_at.desc()",
    )

    @property
    def is_low_stock(self) -> bool:
        return float(self.stock or 0) <= float(self.min_stock or 0)

    @property
    def label(self) -> str:
        parts = [self.material_type, self.name]
        if self.size:
            parts.append(self.size)
        if self.thickness:
            parts.append(self.thickness)
        if self.color:
            parts.append(self.color)
        return " · ".join(p for p in parts if p)
