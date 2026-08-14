from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class StoreHomeSettings(Base):
    """Opciones de publicidad / secciones del home (fila única id=1)."""

    __tablename__ = "store_home_settings"

    id = Column(Integer, primary_key=True)

    show_top_bar = Column(Boolean, default=True, nullable=False)
    top_bar_left = Column(String(200), nullable=True)
    top_bar_right = Column(String(200), nullable=True)

    accent_color = Column(String(20), nullable=True)

    feature_1_title = Column(String(80), nullable=True)
    feature_1_text = Column(String(200), nullable=True)
    feature_2_title = Column(String(80), nullable=True)
    feature_2_text = Column(String(200), nullable=True)
    feature_3_title = Column(String(80), nullable=True)
    feature_3_text = Column(String(200), nullable=True)

    show_categories = Column(Boolean, default=True, nullable=False)
    featured_categories = Column(Text, nullable=True)  # "Bases de MDF, Toppers, ..."

    show_featured_products = Column(Boolean, default=True, nullable=False)
    featured_product_ids = Column(Text, nullable=True)  # "12,45,7"

    show_trust_bar = Column(Boolean, default=True, nullable=False)
    trust_1_title = Column(String(80), nullable=True)
    trust_1_text = Column(String(160), nullable=True)
    trust_2_title = Column(String(80), nullable=True)
    trust_2_text = Column(String(160), nullable=True)
    trust_3_title = Column(String(80), nullable=True)
    trust_3_text = Column(String(160), nullable=True)
    trust_4_title = Column(String(80), nullable=True)
    trust_4_text = Column(String(160), nullable=True)

    show_newsletter = Column(Boolean, default=True, nullable=False)
    newsletter_title = Column(String(160), nullable=True)

    footer_blurb = Column(Text, nullable=True)
    contact_address = Column(String(255), nullable=True)
    contact_phone = Column(String(80), nullable=True)
    contact_email = Column(String(120), nullable=True)
    contact_hours = Column(String(120), nullable=True)
    contact_whatsapp = Column(String(40), nullable=True)
    social_instagram = Column(String(255), nullable=True)
    social_facebook = Column(String(255), nullable=True)
    social_tiktok = Column(String(255), nullable=True)

    # Enlaces extra del menú: "Bases de MDF|/tienda?category=Bases de MDF"
    nav_extra_links = Column(Text, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
