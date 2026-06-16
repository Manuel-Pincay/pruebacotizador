from sqlalchemy import Column, Integer, String
from app.database import Base

class ProductMaterial(Base):

    __tablename__ = "product_materials"

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String,
        unique=True
    )