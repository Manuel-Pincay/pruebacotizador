from sqlalchemy import Column, Integer, String

from app.database import Base


class UsbReference(Base):
    """Referencias USB usadas en diseño / fabricación."""

    __tablename__ = "usb_references"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
