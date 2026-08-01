"""Aplica en BD la configuración SRI según factura PRODUCCIÓN de referencia (reporte.pdf)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.company_config import CompanyConfig
from app.models.sri_emission_point import SriEmissionPoint
from app.models.sri_establishment import SriEstablishment
from app.services.sri_sequence_service import update_sequence_manual
from app.utils.sri_production_reference import PRODUCTION_INVOICE_REFERENCE as REF


def main(apply: bool = False):
    db = SessionLocal()
    try:
        config = db.query(CompanyConfig).first()
        if not config:
            print("ERROR: No hay company_config.")
            return 1

        changes = []
        checks = [
            ("sri_ambiente", config.sri_ambiente, REF["ambiente"]),
            ("sri_ruc", config.sri_ruc, REF["ruc"]),
            ("sri_razon_social", config.sri_razon_social, REF["razon_social"]),
            ("sri_direccion_matriz", config.sri_direccion_matriz, REF["direccion_matriz"]),
            ("sri_contribuyente_rimpe", config.sri_contribuyente_rimpe, REF["contribuyente_rimpe"]),
            ("sri_tipo_emision", config.sri_tipo_emision or "NORMAL", REF["tipo_emision"]),
        ]
        for field, current, expected in checks:
            cur = (current or "").strip()
            exp = (expected or "").strip()
            ok = cur == exp
            print(f"{'OK' if ok else '!!'} {field}: {cur!r} → {exp!r}")
            if not ok:
                changes.append(field)

        est = db.query(SriEstablishment).filter(SriEstablishment.codigo == REF["establecimiento"]).first()
        if est:
            cur_dir = (est.direccion or "").strip()
            exp_dir = REF["direccion_sucursal"]
            ok = cur_dir == exp_dir
            print(f"{'OK' if ok else '!!'} establecimiento.direccion: {cur_dir!r} → {exp_dir!r}")
            if not ok:
                changes.append("establecimiento.direccion")
        else:
            print("!! establecimiento 001 no encontrado")
            changes.append("establecimiento")

        pto = None
        if est:
            pto = (
                db.query(SriEmissionPoint)
                .filter(
                    SriEmissionPoint.establishment_id == est.id,
                    SriEmissionPoint.codigo == REF["punto_emision"],
                )
                .first()
            )
        if pto:
            from app.services.sri_sequence_service import peek_next_secuencial

            next_seq = int(peek_next_secuencial(db, REF["establecimiento"], REF["punto_emision"]))
            ok = next_seq == REF["proximo_secuencial"]
            print(
                f"{'OK' if ok else '!!'} proximo_secuencial: {next_seq} → {REF['proximo_secuencial']}"
            )
            if not ok:
                changes.append("secuencial")
        else:
            print("!! punto emision 001 no encontrado")
            changes.append("punto_emision")

        if not changes:
            print("\n✓ Configuración ya coincide con la factura de referencia.")
            return 0

        if not apply:
            print(f"\nHay {len(changes)} diferencia(s). Ejecute con --apply para corregir.")
            return 2

        config.sri_ambiente = REF["ambiente"]
        config.sri_ruc = REF["ruc"]
        config.sri_razon_social = REF["razon_social"]
        config.sri_nombre_comercial = None
        config.sri_direccion_matriz = REF["direccion_matriz"]
        config.sri_contribuyente_rimpe = REF["contribuyente_rimpe"]
        config.sri_tipo_emision = REF["tipo_emision"]
        config.sri_obligado_contabilidad = REF["obligado_contabilidad"]
        config.sri_active = True

        if est:
            est.direccion = REF["direccion_sucursal"]
        if pto:
            update_sequence_manual(db, pto.id, REF["proximo_secuencial"])

        db.commit()
        print("\n✓ Configuración aplicada según factura PRODUCCIÓN 001-001-000000022.")
        print("  Anule borradores viejos y cree una factura nueva antes de emitir.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    apply_flag = "--apply" in sys.argv
    raise SystemExit(main(apply=apply_flag))
