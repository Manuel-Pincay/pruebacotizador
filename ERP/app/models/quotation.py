from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Float
from sqlalchemy import String
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Date

from sqlalchemy.orm import relationship

from datetime import datetime

from app.database import Base


class Quotation(Base):

    __tablename__ = "quotations"

    id = Column(Integer, primary_key=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id")
    )
    subtotal = Column(Float)
    discount = Column(Float)
    iva = Column(Float)
    total = Column(Float)
    shipping_cost = Column(Float, default=0)
    status = Column(String)
    # Origen: erp (staff) | store (cliente en tienda)
    source = Column(String(20), default="erp", nullable=False)
    # Token para que el cliente vea su pedido sin login (solo tienda)
    store_access_token = Column(String(64), nullable=True, unique=True, index=True)
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_client_id = Column(
        Integer,
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
    )
    delivery_date = Column(Date)
    design_file = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    client = relationship("Client", foreign_keys=[client_id])
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    created_by_client = relationship(
        "Client",
        foreign_keys=[created_by_client_id],
    )
    items = relationship(
        "QuotationItem",
        back_populates="quotation",
    )
    payments = relationship(
        "QuotationPayment",
        back_populates="quotation",
        cascade="all, delete-orphan",
    )
    designs = relationship(
        "QuotationDesign",
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationDesign.sort_order",
    )
    production_tracking = relationship(
        "ProductionTracking",
        back_populates="quotation",
        uselist=False,
        cascade="all, delete-orphan",
    )
    production_order = relationship(
        "ProductionOrder",
        back_populates="quotation",
        uselist=False,
        cascade="all, delete-orphan",
    )
    shipments = relationship(
        "Shipment",
        back_populates="quotation",
        cascade="all, delete-orphan",
    )
    electronic_invoice = relationship(
        "ElectronicInvoice",
        back_populates="quotation",
        uselist=False,
    )
    events = relationship(
        "QuotationEvent",
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationEvent.created_at.desc()",
    )

    @property
    def total_paid(self) -> float:
        """Solo abonos confirmados (pendientes de tienda no cuentan)."""
        return sum(
            float(payment.amount or 0)
            for payment in self.payments
            if (getattr(payment, "verification_status", None) or "confirmed")
            == "confirmed"
        )

    @property
    def amount_pending_verification(self) -> float:
        return sum(
            float(payment.amount or 0)
            for payment in self.payments
            if (getattr(payment, "verification_status", None) or "") == "pending"
        )

    @property
    def pending_balance(self) -> float:
        return float(self.total or 0) - self.total_paid

    @property
    def open_balance_for_new_payment(self) -> float:
        return max(
            0.0,
            float(self.total or 0) - self.total_paid - self.amount_pending_verification,
        )

    @property
    def payment_status(self) -> str:
        """sin_abono | parcial | pagada"""
        paid = self.total_paid
        total = float(self.total or 0)
        if paid <= 0:
            return "sin_abono"
        if paid >= total:
            return "pagada"
        return "parcial"

    @property
    def has_pending_payment_verification(self) -> bool:
        return any(
            (getattr(p, "verification_status", None) or "") == "pending"
            for p in self.payments
        )