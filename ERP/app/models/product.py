from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import Boolean

from app.database import Base


class Product(Base):

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)

    code = Column(String)
    name = Column(String)

    description = Column(String)

    category = Column(String)

    material = Column(String)
    color = Column(String)

    size = Column(String)

    thickness = Column(String)

    price = Column(Float)

    cost = Column(Float)

    stock = Column(Integer)

    custom = Column(Boolean)

    image = Column(String)