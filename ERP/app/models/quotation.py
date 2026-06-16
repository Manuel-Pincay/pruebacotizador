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
    delivery_date = Column(Date)
    design_file = Column(String)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    client = relationship("Client")
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

    @property
    def total_paid(self) -> float:
        return sum(float(payment.amount or 0) for payment in self.payments)

    @property
    def pending_balance(self) -> float:
        return float(self.total or 0) - self.total_paid

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