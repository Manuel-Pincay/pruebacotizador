from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import DateTime
from datetime import datetime

from app.database import Base


class CompanyConfig(Base):

    __tablename__ = "company_config"

    id = Column(Integer, primary_key=True)

    company_name = Column(String, default="SISTEMA ERP")

    logo = Column(String, nullable=True)

    primary_color = Column(String, default="#7C3AED")

    secondary_color = Column(String, default="#E9D5FF")

    accent_color = Column(String, default="#4C1D95")

    font_color = Column(String, default="#333333")

    quotation_validity_days = Column(Integer, default=15)

    quotation_footer_text = Column(String, default="Gracias por confiar en SISTEMA ERP.")

    iva_default = Column(Integer, default=19)

    guide_sender_name = Column(String, nullable=True)
    guide_sender_city = Column(String, default="Manta")
    guide_sender_region = Column(String, default="Ecuador")
    guide_sender_phone = Column(String, nullable=True)
    guide_sender_address = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.now)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
