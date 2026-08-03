from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime
from datetime import datetime

from app.database import Base


class CompanyConfig(Base):

    __tablename__ = "company_config"

    id = Column(Integer, primary_key=True)

    company_name = Column(String, default="SISTEMA ERP")

    logo = Column(String, nullable=True)

    company_icon = Column(String, nullable=True)

    primary_color = Column(String, default="#7C3AED")

    secondary_color = Column(String, default="#E9D5FF")

    accent_color = Column(String, default="#4C1D95")

    font_color = Column(String, default="#333333")

    quotation_validity_days = Column(Integer, default=15)

    quotation_footer_text = Column(String, default="Gracias por confiar en SISTEMA ERP.")

    iva_default = Column(Integer, default=0)

    guide_sender_name = Column(String, nullable=True)
    guide_sender_city = Column(String, default="Manta")
    guide_sender_region = Column(String, default="Ecuador")
    guide_sender_phone = Column(String, nullable=True)
    guide_sender_address = Column(String, nullable=True)

    # Colores de la etiqueta / guía de envío
    guide_accent_color = Column(String(20), default="#d6452a")
    guide_border_color = Column(String(20), default="#8a97a8")
    guide_muted_color = Column(String(20), default="#6b7785")

    # Facturación electrónica SRI
    sri_ruc = Column(String(13), nullable=True)
    sri_razon_social = Column(String(300), nullable=True)
    sri_nombre_comercial = Column(String(300), nullable=True)
    sri_direccion_matriz = Column(String(500), nullable=True)
    sri_obligado_contabilidad = Column(Boolean, default=False)
    sri_contribuyente_especial = Column(String(20), nullable=True)
    sri_contribuyente_rimpe = Column(String(100), nullable=True)
    sri_ambiente = Column(String(20), default="PRUEBAS")
    sri_tipo_emision = Column(String(20), default="NORMAL")
    sri_email_notificacion = Column(String(255), nullable=True)
    sri_default_establishment = Column(String(3), nullable=True)
    sri_default_emission_point = Column(String(3), nullable=True)
    sri_active = Column(Boolean, default=False)

    billing_email_subject = Column(String(255), nullable=True)
    billing_email_body = Column(Text, nullable=True)
    billing_auto_send_email = Column(Boolean, default=True)

    smtp_enabled = Column(Boolean, default=False)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String(255), nullable=True)
    smtp_password_encrypted = Column(String(512), nullable=True)
    smtp_from = Column(String(255), nullable=True)
    smtp_use_tls = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.now)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
