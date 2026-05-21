from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String)
    company = Column(String)
    ruc_ci = Column(String)

    phone = Column(String)
    email = Column(String)
    address = Column(Text)

    client_type = Column(String)

    observations = Column(Text)