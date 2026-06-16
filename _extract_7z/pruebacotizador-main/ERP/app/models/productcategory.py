from sqlalchemy import Column, Integer, String
from app.database import Base

class ProductCategory(Base):

    __tablename__ = "product_categories"

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String,
        unique=True
    )