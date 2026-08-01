"""Diagnóstico de emisión SRI — no imprime contraseñas ni certificados."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models.company_config import CompanyConfig
from app.models.electronic_invoice import ElectronicInvoice
from app.models.sri_certificate import SriCertificate
from app.services.sri_client_service import consultar_autorizacion, enviar_comprobante
from app.services.sri_emission_service import _build_xml
from app.services.sri_sign_service import sign_invoice_xml, SriSignError
from app.utils.encryption import decrypt_bytes, decrypt_text
from app.utils.sri_production_reference import PRODUCTION_INVOICE_REFERENCE as PROD_REF


def main(invoice_id: int | None = None):
    db = SessionLocal()
    try:
        q = db.query(ElectronicInvoice).options(
            joinedload(ElectronicInvoice.client),
            joinedload(ElectronicInvoice.lines),
        )
        inv = q.filter(ElectronicInvoice.id == invoice_id).first() if invoice_id else q.order_by(ElectronicInvoice.id.desc()).first()
        if not inv:
            print("No hay facturas.")
            return 1

        cfg = db.query(CompanyConfig).first()
        cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
        amb = (cfg.sri_ambiente if cfg else None) or "PRUEBAS"

        print(f"=== Factura #{inv.id} {inv.numero_comprobante} ({inv.estado}) ===")
        print(f"Ambiente config: {amb}")
        print(f"Clave acceso: {inv.clave_acceso}")
        print(f"Clave dígito 24 (ambiente): {inv.clave_acceso[23]}")

        print("\n--- Referencia PRODUCCIÓN (reporte.pdf) ---")
        print(f"Última autorizada: {PROD_REF['numero']} | próximo sec: {PROD_REF['proximo_secuencial']:09d}")
        print(f"Ambiente ref: {PROD_REF['ambiente']} | RIMPE: {PROD_REF['contribuyente_rimpe'][:40]}…")
        mismatches = []
        if amb != PROD_REF["ambiente"]:
            mismatches.append(f"ambiente config={amb} (ref={PROD_REF['ambiente']})")
        if (cfg.sri_razon_social or "").strip() != PROD_REF["razon_social"]:
            mismatches.append("razón social distinta a la factura autorizada")
        if not (cfg.sri_contribuyente_rimpe or "").strip():
            mismatches.append("falta contribuyente RIMPE")
        if inv.clave_acceso and len(inv.clave_acceso) >= 24 and inv.clave_acceso[23] != "2":
            mismatches.append("clave generada en PRUEBAS (dígito 24 = 1)")
        if mismatches:
            print("⚠ Diferencias vs referencia:")
            for m in mismatches:
                print(f"  • {m}")
            print("  Ejecute: python scripts/apply_production_reference.py --apply")
        else:
            print("✓ Config alineada con factura de referencia.")

        auth = consultar_autorizacion(inv.clave_acceso, amb, cfg.sri_tipo_emision or "NORMAL")
        print(f"Consulta autorización SRI: {auth.get('estado')}")

        if not cert:
            print("ERROR: Sin certificado .p12 configurado.")
            return 1

        xml = _build_xml(inv, cfg, db)
        out_dir = ROOT / "scripts" / "sri-debug"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"invoice_{inv.id}_unsigned.xml").write_text(xml, encoding="utf-8")
        print(f"XML sin firmar: {len(xml)} bytes → scripts/sri-debug/invoice_{inv.id}_unsigned.xml")

        try:
            p12 = decrypt_bytes(cert.encrypted_p12)
            pwd = decrypt_text(cert.encrypted_password)
            signed = sign_invoice_xml(xml, p12, pwd)
        except SriSignError as exc:
            print(f"ERROR firma: {exc}")
            return 1

        (out_dir / f"invoice_{inv.id}_signed.xml").write_text(signed, encoding="utf-8")
        print(f"XML firmado: {len(signed)} bytes → scripts/sri-debug/invoice_{inv.id}_signed.xml")
        print(f"Contiene Signature: {'<ds:Signature' in signed or 'Signature' in signed}")

        try:
            recepcion = enviar_comprobante(signed, amb, cfg.sri_tipo_emision or "NORMAL", retries=1)
            print("RECEPCIÓN OK:", json.dumps(recepcion, ensure_ascii=False))
        except Exception as exc:
            print(f"RECEPCIÓN FALLO: {exc}")
            return 1

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    iid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    raise SystemExit(main(iid))
