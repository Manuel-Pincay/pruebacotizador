from sqlalchemy import Column, Integer, String

from app.database import Base


class ProductSize(Base):
    """Medidas de diseño / fabricación (ej. 120x90, A4)."""

    __tablename__ = "product_sizes"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
