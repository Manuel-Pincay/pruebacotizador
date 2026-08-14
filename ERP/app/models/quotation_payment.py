from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from app.database import Base

# confirmed = cuenta como abono | pending = esperando verificación | rejected = no válido
PAYMENT_STATUS_CONFIRMED = "confirmed"
PAYMENT_STATUS_PENDING = "pending"
PAYMENT_STATUS_REJECTED = "rejected"


class QuotationPayment(Base):

    __tablename__ = "quotation_payments"

    id = Column(Integer, primary_key=True)

    quotation_id = Column(
        Integer,
        ForeignKey("quotations.id"),
        nullable=False,
    )

    amount = Column(Numeric(12, 2), nullable=False)

    payment_date = Column(DateTime, nullable=False)

    payment_method = Column(String(50))

    reference = Column(String(100))

    notes = Column(Text)

    transfer_receipt = Column(String(255))

    verification_status = Column(
        String(20),
        default=PAYMENT_STATUS_CONFIRMED,
        nullable=False,
    )
    verified_at = Column(DateTime, nullable=True)
    verified_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    quotation = relationship(
        "Quotation",
        back_populates="payments",
    )
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])

    @property
    def is_confirmed(self) -> bool:
        return (self.verification_status or PAYMENT_STATUS_CONFIRMED) == PAYMENT_STATUS_CONFIRMED

    @property
    def is_pending(self) -> bool:
        return (self.verification_status or "") == PAYMENT_STATUS_PENDING

    @property
    def verification_label(self) -> str:
        st = self.verification_status or PAYMENT_STATUS_CONFIRMED
        return {
            PAYMENT_STATUS_PENDING: "Esperando verificación",
            PAYMENT_STATUS_CONFIRMED: "Pago confirmado",
            PAYMENT_STATUS_REJECTED: "Pago rechazado",
        }.get(st, st)
