from sqlalchemy import Column, Integer, String
from app.database import Base

class ProductThickness(Base):

    __tablename__ = "product_thicknesses"

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String,
        unique=True
    )