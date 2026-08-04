from sqlalchemy.orm import Session

from app.models.quotation_event import QuotationEvent


def log_quotation_event(
    db: Session,
    quotation_id: int,
    action: str,
    description: str = "",
    user_id: int | None = None,
) -> None:
    """Registra un evento en la bitácora de la cotización."""
    try:
        db.add(
            QuotationEvent(
                quotation_id=quotation_id,
                user_id=user_id,
                action=action,
                description=description or action,
            )
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
