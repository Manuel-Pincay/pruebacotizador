from app.database import SessionLocal
from app.models.company_config import CompanyConfig


def get_global_config():
    """Return a simple object with the company config or None."""
    db = SessionLocal()
    try:
        config = db.query(CompanyConfig).first()
        return {"config": config}
    finally:
        db.close()
