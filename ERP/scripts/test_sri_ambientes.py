"""Compara recepción SRI en PRUEBAS vs PRODUCCIÓN con el mismo XML firmado."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.models.sri_certificate import SriCertificate
from app.services.sri_client_service import consultar_autorizacion, enviar_comprobante
from app.services.sri_emission_service import _build_xml
from app.services.sri_sign_service import sign_invoice_xml
from app.utils.encryption import decrypt_bytes, decrypt_text
from sqlalchemy.orm import joinedload


def main(invoice_id: int = 9):
    db = SessionLocal()
    try:
        inv = (
            db.query(ElectronicInvoice)
            .options(joinedload(ElectronicInvoice.client), joinedload(ElectronicInvoice.lines))
            .filter(ElectronicInvoice.id == invoice_id)
            .first()
        )
        cfg = db.query(CompanyConfig).first()
        cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
        if not inv or not cfg or not cert:
            print("Faltan datos (factura/config/certificado).")
            return 1

        print(f"Factura #{inv.id} {inv.numero_comprobante}")
        print(f"Clave: {inv.clave_acceso} (ambiente dígito 24 = {inv.clave_acceso[23]})")
        print()

        xml = _build_xml(inv, cfg, db)
        rimpe_ok = "RÉGIMEN" in xml and "RÃ" not in xml
        print(f"[1] XML sin firmar: {len(xml)} bytes | RIMPE OK: {rimpe_ok}")
        print(f"    ambiente tag: {'<ambiente>2</ambiente>' if '<ambiente>2</ambiente>' in xml else '<ambiente>1</ambiente>'}")

        signed = sign_invoice_xml(xml, decrypt_bytes(cert.encrypted_p12), decrypt_text(cert.encrypted_password))
        rimpe_signed = "RÉGIMEN" in signed and "RÃ" not in signed
        print(f"[2] XML firmado: {len(signed)} bytes | RIMPE OK: {rimpe_signed}")
        print(f"    Signature: {'<ds:Signature' in signed}")
        print()

        for amb in ("PRUEBAS", "PRODUCCION"):
            print(f"--- Ambiente {amb} ---")
            try:
                auth = consultar_autorizacion(inv.clave_acceso, amb, "NORMAL")
                print(f"  Consulta autorización: {auth.get('estado')}")
            except Exception as exc:
                print(f"  Consulta autorización: ERROR {exc}")

            try:
                recep = enviar_comprobante(signed, amb, "NORMAL", retries=1)
                print(f"  Recepción: {recep.get('estado')}")
                for m in recep.get("mensajes") or []:
                    print(f"    • [{m.get('identificador')}] {m.get('mensaje')}")
                    if m.get("informacion_adicional"):
                        print(f"      {m['informacion_adicional'][:200]}")
            except Exception as exc:
                print(f"  Recepción: ERROR — {str(exc)[:250]}")
            print()

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    iid = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    raise SystemExit(main(iid))
