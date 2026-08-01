from sqlalchemy.orm import Session

from app.models.electronic_invoice import ElectronicInvoice
from app.models.sri_emission_point import SriEmissionPoint
from app.models.sri_establishment import SriEstablishment
from app.models.sri_sequence import SriSequence
from app.utils.clave_acceso import generar_clave_acceso


def get_or_create_sequence(db: Session, emission_point_id: int, tipo="FACTURA") -> SriSequence:
    seq = (
        db.query(SriSequence)
        .filter(
            SriSequence.emission_point_id == emission_point_id,
            SriSequence.tipo_comprobante == tipo,
        )
        .first()
    )
    if not seq:
        seq = SriSequence(emission_point_id=emission_point_id, tipo_comprobante=tipo, ultimo_numero=0)
        db.add(seq)
        db.flush()
    return seq


def peek_next_secuencial(db: Session, codigo_establecimiento: str, codigo_punto_emision: str, tipo="FACTURA") -> str:
    """Vista previa del siguiente secuencial sin consumirlo."""
    est = db.query(SriEstablishment).filter(SriEstablishment.codigo == codigo_establecimiento).first()
    if not est:
        raise ValueError(f"Establecimiento {codigo_establecimiento} no configurado.")
    pto = (
        db.query(SriEmissionPoint)
        .filter(
            SriEmissionPoint.establishment_id == est.id,
            SriEmissionPoint.codigo == codigo_punto_emision,
        )
        .first()
    )
    if not pto:
        raise ValueError(f"Punto de emisión {codigo_punto_emision} no configurado.")
    seq = get_or_create_sequence(db, pto.id, tipo)
    return str(int(seq.ultimo_numero or 0) + 1).zfill(9)


def next_secuencial(db: Session, codigo_establecimiento: str, codigo_punto_emision: str, tipo="FACTURA") -> str:
    est = db.query(SriEstablishment).filter(SriEstablishment.codigo == codigo_establecimiento).first()
    if not est:
        raise ValueError(f"Establecimiento {codigo_establecimiento} no configurado.")
    pto = (
        db.query(SriEmissionPoint)
        .filter(
            SriEmissionPoint.establishment_id == est.id,
            SriEmissionPoint.codigo == codigo_punto_emision,
        )
        .first()
    )
    if not pto:
        raise ValueError(f"Punto de emisión {codigo_punto_emision} no configurado.")

    seq = get_or_create_sequence(db, pto.id, tipo)
    seq.ultimo_numero = int(seq.ultimo_numero or 0) + 1
    db.flush()
    return str(seq.ultimo_numero).zfill(9)


def check_sequence_discrepancy(db: Session, codigo_establecimiento: str, codigo_punto_emision: str) -> dict | None:
    est = db.query(SriEstablishment).filter(SriEstablishment.codigo == codigo_establecimiento).first()
    if not est:
        return None
    pto = (
        db.query(SriEmissionPoint)
        .filter(
            SriEmissionPoint.establishment_id == est.id,
            SriEmissionPoint.codigo == codigo_punto_emision,
        )
        .first()
    )
    if not pto:
        return None
    seq = get_or_create_sequence(db, pto.id, "FACTURA")
    configured_next = int(seq.ultimo_numero or 0) + 1

    last_invoice = (
        db.query(ElectronicInvoice)
        .filter(
            ElectronicInvoice.codigo_establecimiento == codigo_establecimiento,
            ElectronicInvoice.codigo_punto_emision == codigo_punto_emision,
        )
        .order_by(ElectronicInvoice.secuencial.desc())
        .first()
    )
    if not last_invoice:
        return None

    last_num = int(last_invoice.secuencial)
    if configured_next <= last_num:
        return {
            "secuencia_local": str(configured_next).zfill(9),
            "secuencia_esperada": str(last_num + 1).zfill(9),
            "ultimo_emitido": last_invoice.secuencial,
        }
    return None


def update_sequence_manual(db: Session, emission_point_id: int, proximo_secuencial: int, tipo="FACTURA"):
    proximo = int(proximo_secuencial)
    if proximo < 1:
        raise ValueError("El secuencial debe ser mayor a cero.")
    seq = get_or_create_sequence(db, emission_point_id, tipo)
    seq.ultimo_numero = proximo - 1
    db.commit()
    return seq


def reserve_clave_acceso(
    db,
    config,
    codigo_establecimiento: str,
    codigo_punto_emision: str,
    fecha_emision,
    tipo="FACTURA",
):
    secuencial = next_secuencial(db, codigo_establecimiento, codigo_punto_emision, tipo)
    clave = generar_clave_acceso(
        fecha_emision=fecha_emision,
        tipo_comprobante=tipo,
        ruc=config.sri_ruc,
        ambiente=config.sri_ambiente or "PRUEBAS",
        codigo_establecimiento=codigo_establecimiento,
        codigo_punto_emision=codigo_punto_emision,
        secuencial=secuencial,
        tipo_emision=config.sri_tipo_emision or "NORMAL",
    )
    return secuencial, clave
