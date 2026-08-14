from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class StoreSlide(Base):
    """Slide del carrusel hero de la tienda."""

    __tablename__ = "store_slides"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    subtitle = Column(String(400), nullable=True)
    cta_text = Column(String(80), nullable=True)
    cta_url = Column(String(255), nullable=True)
    image = Column(String(255), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
