from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class SriEstablishment(Base):
    __tablename__ = "sri_establishments"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(3), nullable=False, unique=True)
    nombre = Column(String(255), nullable=True)
    direccion = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    emission_points = relationship(
        "SriEmissionPoint",
        back_populates="establishment",
        cascade="all, delete-orphan",
    )
