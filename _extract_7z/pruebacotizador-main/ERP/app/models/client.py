from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String)
    company = Column(String)
    ruc_ci = Column(String, unique=True)
    phone = Column(String)
    email = Column(String)
    address = Column(Text)
    client_type = Column(String)
    observations = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
