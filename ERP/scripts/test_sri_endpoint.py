"""Prueba rápida de endpoints SRI recepción."""
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.sri_client_service import _post_soap, SRI_NS

URLS = {
    "PRUEBAS_OFFLINE": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline",
    "PRUEBAS_ONLINE": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes",
    "PROD_OFFLINE": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline",
}


def probe(name: str, url: str, b64: str):
    env = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="{SRI_NS['recepcion']}">
  <soap:Body>
    <ec:validarComprobante>
      <xml>{b64}</xml>
    </ec:validarComprobante>
  </soap:Body>
</soap:Envelope>"""
    try:
        text = _post_soap(url, env)
        print(f"[{name}] OK → {text[:180]}...")
    except Exception as exc:
        print(f"[{name}] ERR → {str(exc)[:200]}")


if __name__ == "__main__":
    b64 = base64.b64encode(b"<?xml version='1.0'?><x/>").decode("ascii")
    for name, url in URLS.items():
        probe(name, url, b64)

    signed = ROOT / "scripts" / "sri-debug" / "invoice_3_signed.xml"
    if signed.exists():
        real = base64.b64encode(signed.read_bytes()).decode("ascii")
        print("\n--- Con XML firmado real ---")
        probe("PRUEBAS_OFFLINE_REAL", URLS["PRUEBAS_OFFLINE"], real)
        probe("PRUEBAS_ONLINE_REAL", URLS["PRUEBAS_ONLINE"], real)
