import base64
import json
import subprocess
from pathlib import Path

SIGNER_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "sri-signer"
SIGN_SCRIPT = SIGNER_DIR / "sign.js"


class SriSignError(Exception):
    pass


def sign_invoice_xml(xml_content: str, p12_bytes: bytes, password: str) -> str:
    return sign_comprobante_xml(xml_content, p12_bytes, password, "FACTURA")


def sign_comprobante_xml(
    xml_content: str, p12_bytes: bytes, password: str, tipo_comprobante: str = "FACTURA"
) -> str:
    if not SIGN_SCRIPT.exists():
        raise SriSignError(
            "Firmador SRI no instalado. Ejecute: cd ERP/scripts/sri-signer && npm install"
        )
    payload = json.dumps(
        {
            "xml": xml_content,
            "p12": base64.b64encode(p12_bytes).decode("ascii"),
            "password": password,
            "tipo": (tipo_comprobante or "FACTURA").upper(),
        }
    )
    try:
        result = subprocess.run(
            ["node", str(SIGN_SCRIPT)],
            input=payload.encode("utf-8"),
            capture_output=True,
            timeout=60,
            cwd=str(SIGNER_DIR),
        )
    except FileNotFoundError as exc:
        raise SriSignError("Node.js no está instalado. Requerido para firmar comprobantes SRI.") from exc
    except subprocess.TimeoutExpired as exc:
        raise SriSignError("Tiempo de espera agotado al firmar el XML.") from exc

    if result.returncode != 0:
        err = (result.stderr or result.stdout or b"Error desconocido al firmar").decode("utf-8", errors="replace").strip()
        raise SriSignError(err)

    try:
        data = json.loads(result.stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SriSignError(f"Respuesta inválida del firmador: {result.stdout[:200]}") from exc

    if not data.get("signedXml"):
        raise SriSignError(data.get("error") or "No se obtuvo XML firmado")
    return data["signedXml"]
