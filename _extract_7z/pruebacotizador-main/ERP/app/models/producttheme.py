from sqlalchemy import Column, Integer, String
from app.database import Base

class ProductTheme(Base):

    __tablename__ = "product_themes"

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String,
        unique=True
    )