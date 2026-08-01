from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


INVOICE_STATES = (
    "BORRADOR",
    "PENDIENTE_ENVIO",
    "ENVIANDO",
    "RECIBIDA",
    "AUTORIZADA",
    "RECHAZADA",
    "ERROR",
    "ANULADA",
)


class ElectronicInvoice(Base):
    __tablename__ = "electronic_invoices"

    id = Column(Integer, primary_key=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"), nullable=True, unique=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    tipo_comprobante = Column(String(20), default="FACTURA", nullable=False)
    clave_acceso = Column(String(49), unique=True, nullable=False)
    secuencial = Column(String(9), nullable=False)
    codigo_establecimiento = Column(String(3), nullable=False)
    codigo_punto_emision = Column(String(3), nullable=False)
    fecha_emision = Column(DateTime, nullable=False)

    invoice_modificado_id = Column(Integer, ForeignKey("electronic_invoices.id"), nullable=True)
    motivo = Column(String(300), nullable=True)
    cod_doc_modificado = Column(String(2), nullable=True)
    num_doc_modificado = Column(String(20), nullable=True)
    fecha_emision_doc_sustento = Column(DateTime, nullable=True)

    subtotal_sin_impuestos = Column(Float, default=0)
    subtotal_iva = Column(Float, default=0)
    descuento = Column(Float, default=0)
    propina = Column(Float, default=0)
    importe_total = Column(Float, default=0)
    moneda = Column(String(10), default="DOLAR")

    pagos_json = Column(Text, nullable=True)
    info_adicional_json = Column(Text, nullable=True)

    estado = Column(String(30), default="BORRADOR", nullable=False)
    xml_generado = Column(Text, nullable=True)
    xml_firmado = Column(Text, nullable=True)
    xml_autorizado = Column(Text, nullable=True)
    numero_autorizacion = Column(String(64), nullable=True)
    fecha_autorizacion = Column(DateTime, nullable=True)
    mensajes_sri_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    email_sent_at = Column(DateTime, nullable=True)
    email_sent_to_json = Column(Text, nullable=True)
    email_last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    quotation = relationship("Quotation", back_populates="electronic_invoice", uselist=False)
    client = relationship("Client")
    created_by = relationship("User")
    lines = relationship(
        "ElectronicInvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="ElectronicInvoiceLine.id",
    )
    documento_modificado = relationship(
        "ElectronicInvoice",
        remote_side="ElectronicInvoice.id",
        foreign_keys=[invoice_modificado_id],
        backref="notas_credito",
    )

    @property
    def is_nota_credito(self) -> bool:
        return (self.tipo_comprobante or "").upper() == "NOTA_CREDITO"

    @property
    def is_factura(self) -> bool:
        return (self.tipo_comprobante or "FACTURA").upper() == "FACTURA"

    @property
    def tipo_label(self) -> str:
        if self.is_nota_credito:
            return "Nota de crédito"
        return "Factura"

    @property
    def nota_credito_autorizada(self):
        for nc in self.notas_credito or []:
            if nc.estado == "AUTORIZADA":
                return nc
        return None

    @property
    def numero_comprobante(self) -> str:
        return f"{self.codigo_establecimiento}-{self.codigo_punto_emision}-{self.secuencial}"
