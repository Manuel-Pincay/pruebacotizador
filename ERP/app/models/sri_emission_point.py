from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class SriEmissionPoint(Base):
    __tablename__ = "sri_emission_points"

    id = Column(Integer, primary_key=True)
    establishment_id = Column(Integer, ForeignKey("sri_establishments.id"), nullable=False)
    codigo = Column(String(3), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    establishment = relationship("SriEstablishment", back_populates="emission_points")
    sequences = relationship(
        "SriSequence",
        back_populates="emission_point",
        cascade="all, delete-orphan",
    )
