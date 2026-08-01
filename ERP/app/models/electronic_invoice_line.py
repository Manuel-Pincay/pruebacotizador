from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class ElectronicInvoiceLine(Base):
    __tablename__ = "electronic_invoice_lines"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("electronic_invoices.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    quotation_item_id = Column(Integer, ForeignKey("quotation_items.id"), nullable=True)

    codigo_principal = Column(String(50), nullable=False)
    codigo_auxiliar = Column(String(50), nullable=True)
    descripcion = Column(String(500), nullable=False)
    cantidad = Column(Float, default=1)
    precio_unitario = Column(Float, default=0)
    descuento = Column(Float, default=0)
    precio_total_sin_impuesto = Column(Float, default=0)
    codigo_iva = Column(String(5), default="0")
    tarifa_iva = Column(Float, default=0)
    valor_iva = Column(Float, default=0)

    invoice = relationship("ElectronicInvoice", back_populates="lines")
    product = relationship("Product")
