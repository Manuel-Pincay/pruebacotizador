from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime
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
    additional_emails_json = Column(Text, nullable=True)
    address = Column(Text)
    client_type = Column(String)
    tipo_identificacion = Column(String(30), default="CEDULA")
    observations = Column(Text)
    # Acceso al portal de tienda
    password_hash = Column(String(255), nullable=True)
    portal_active = Column(Boolean, default=False, nullable=False)
    portal_verify_code = Column(String(10), nullable=True)
    portal_verify_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
