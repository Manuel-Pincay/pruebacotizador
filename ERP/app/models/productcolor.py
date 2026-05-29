from sqlalchemy import Column, Integer, String
from app.database import Base

class ProductColor(Base):

    __tablename__ = "product_colors"

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String,
        unique=True
    )