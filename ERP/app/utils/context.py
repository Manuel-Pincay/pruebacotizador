from app.database import SessionLocal
from app.models.company_config import CompanyConfig
from app.utils.image_storage import logo_image_url


def get_global_config():
    """Return company config and derived UI values."""
    db = SessionLocal()
    try:
        config = db.query(CompanyConfig).first()
        logo_url = (
            logo_image_url(config.company_icon)
            if config and config.company_icon
            else None
        )
        return {"config": config, "logo_url": logo_url}
    finally:
        db.close()
