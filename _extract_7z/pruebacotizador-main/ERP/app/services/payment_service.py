from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.models.quotation import Quotation
from app.models.quotation_payment import QuotationPayment


class PaymentValidationError(Exception):
    """Error de validación al registrar un abono."""


def get_quotation_or_raise(db: Session, quotation_id: int) -> Quotation:
    quotation = db.query(Quotation).filter(Quotation.id == quotation_id).first()
    if not quotation:
        raise PaymentValidationError("Cotización no encontrada.")
    return quotation


def parse_amount(value: str) -> Decimal:
    try:
        amount = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, AttributeError):
        raise PaymentValidationError("El valor del abono no es válido.") from None
    if amount <= 0:
        raise PaymentValidationError("El abono debe ser mayor a cero.")
    return amount.quantize(Decimal("0.01"))


def validate_payment_amount(quotation: Quotation, amount: Decimal) -> None:
    pending = Decimal(str(quotation.pending_balance)).quantize(Decimal("0.01"))
    if amount > pending:
        raise PaymentValidationError(
            f"El abono no puede superar el saldo pendiente (${pending:.2f})."
        )


def serialize_payment(payment: QuotationPayment) -> dict:
    return {
        "id": payment.id,
        "quotation_id": payment.quotation_id,
        "amount": float(payment.amount),
        "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
        "payment_method": payment.payment_method,
        "reference": payment.reference,
        "notes": payment.notes,
        "transfer_receipt": payment.transfer_receipt,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
    }
