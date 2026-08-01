from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class SriSequence(Base):
    __tablename__ = "sri_sequences"

    id = Column(Integer, primary_key=True)
    emission_point_id = Column(Integer, ForeignKey("sri_emission_points.id"), nullable=False)
    tipo_comprobante = Column(String(30), default="FACTURA", nullable=False)
    ultimo_numero = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    emission_point = relationship("SriEmissionPoint", back_populates="sequences")
