from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, LargeBinary, String

from app.database import Base


class SriCertificate(Base):
    __tablename__ = "sri_certificates"

    id = Column(Integer, primary_key=True)
    encrypted_p12 = Column(LargeBinary, nullable=False)
    encrypted_password = Column(String(512), nullable=False)
    subject_common_name = Column(String(255), nullable=True)
    issuer = Column(String(255), nullable=True)
    serial_number = Column(String(128), nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
