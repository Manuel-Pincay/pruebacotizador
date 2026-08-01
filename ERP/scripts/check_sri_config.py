"""Revisa configuración SRI guardada en BD (sin secretos)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.company_config import CompanyConfig
from app.models.sri_certificate import SriCertificate
from app.models.sri_establishment import SriEstablishment
from app.services.sri_config_validator import validate_sri_config
from app.utils.encryption import decrypt_bytes, decrypt_text


def main():
    db = SessionLocal()
    try:
        config = db.query(CompanyConfig).first()
        cert = db.query(SriCertificate).order_by(SriCertificate.id.desc()).first()
        print("=== Config SRI en base de datos ===")
        if not config:
            print("NO HAY CompanyConfig")
            return 1
        fields = [
            "sri_ruc",
            "sri_razon_social",
            "sri_nombre_comercial",
            "sri_direccion_matriz",
            "sri_contribuyente_rimpe",
            "sri_contribuyente_especial",
            "sri_ambiente",
            "sri_tipo_emision",
            "sri_email_notificacion",
            "sri_default_establishment",
            "sri_default_emission_point",
            "sri_obligado_contabilidad",
            "sri_active",
            "iva_default",
        ]
        for f in fields:
            print(f"  {f}: {getattr(config, f)!r}")

        print("\n=== Certificado ===")
        if cert:
            print(f"  id={cert.id} valid_to={cert.valid_to} subject={cert.subject_common_name!r}")
            try:
                p12 = decrypt_bytes(cert.encrypted_p12)
                pwd = decrypt_text(cert.encrypted_password)
                print(f"  descifrado OK (p12={len(p12)} bytes, pwd_len={len(pwd)})")
            except Exception as exc:
                print(f"  ERROR descifrado: {type(exc).__name__}: {exc}")
        else:
            print("  NO configurado")

        print("\n=== Establecimientos ===")
        for est in db.query(SriEstablishment).all():
            print(f"  {est.codigo} nombre={est.nombre!r}")
            print(f"    direccion={est.direccion!r}")
            for pto in est.emission_points:
                for seq in pto.sequences:
                    print(f"    punto {pto.codigo} {seq.tipo_comprobante} ultimo={seq.ultimo_numero}")

        v = validate_sri_config(db, config, cert)
        print(f"\n=== Validación: {'OK lista para emitir' if v.valido else 'PENDIENTE'} ===")
        for e in v.errores:
            print(f"  ERROR: {e.mensaje}")
        for a in v.advertencias:
            print(f"  AVISO: {a.mensaje}")
        return 0 if v.valido else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
