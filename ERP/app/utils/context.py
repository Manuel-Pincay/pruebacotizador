from app.database import SessionLocal
from app.models.company_config import CompanyConfig
from app.utils.image_storage import logo_image_url


def build_empresa_sri(config: CompanyConfig | None) -> dict:
    """Datos del emisor SRI para pantallas de facturación."""
    if not config:
        return {
            "razon_social": "",
            "nombre_comercial": "SISTEMA ERP",
            "ruc": "",
            "direccion_matriz": "",
            "ambiente": "PRUEBAS",
            "email_notificacion": "",
            "tipo_emision": "NORMAL",
        }
    return {
        "razon_social": config.sri_razon_social or config.company_name or "",
        "nombre_comercial": config.sri_nombre_comercial
        or config.sri_razon_social
        or config.company_name
        or "SISTEMA ERP",
        "ruc": config.sri_ruc or "",
        "direccion_matriz": config.sri_direccion_matriz or "",
        "ambiente": config.sri_ambiente or "PRUEBAS",
        "email_notificacion": config.sri_email_notificacion or "",
        "tipo_emision": config.sri_tipo_emision or "NORMAL",
    }


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
        return {
            "config": config,
            "logo_url": logo_url,
            "empresa_sri": build_empresa_sri(config),
        }
    finally:
        db.close()
