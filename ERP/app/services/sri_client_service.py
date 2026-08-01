import base64
import re
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

def _emision_mode(tipo_emision: str | None) -> str:
    return "CONTINGENCIA" if (tipo_emision or "NORMAL").upper() == "CONTINGENCIA" else "NORMAL"


def get_sri_url(servicio: str, ambiente: str, tipo_emision: str | None = "NORMAL") -> str:
    """Como FactuSRI (sri.constants.ts): siempre WS Offline por ambiente."""
    _ = tipo_emision  # reservado; FactuSRI no cambia URL por tipo emisión
    urls = {
        "recepcion": {
            "PRUEBAS": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline",
            "PRODUCCION": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline",
        },
        "autorizacion": {
            "PRUEBAS": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline",
            "PRODUCCION": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline",
        },
    }
    amb = ambiente if ambiente in ("PRUEBAS", "PRODUCCION") else "PRUEBAS"
    return urls[servicio][amb]


# Compatibilidad con código que aún use el dict plano
SRI_URLS = {
    "recepcion": {
        "PRUEBAS": get_sri_url("recepcion", "PRUEBAS", "NORMAL"),
        "PRODUCCION": get_sri_url("recepcion", "PRODUCCION", "NORMAL"),
    },
    "autorizacion": {
        "PRUEBAS": get_sri_url("autorizacion", "PRUEBAS", "NORMAL"),
        "PRODUCCION": get_sri_url("autorizacion", "PRODUCCION", "NORMAL"),
    },
}

SRI_NS = {
    "recepcion": "http://ec.gob.sri.ws.recepcion",
    "autorizacion": "http://ec.gob.sri.ws.autorizacion",
}


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _find_first(root, name: str):
    for el in root.iter():
        if _strip_ns(el.tag) == name:
            return el
    return None


def _normalize_mensajes(raw):
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    result = []
    for m in items:
        if not isinstance(m, dict):
            continue
        result.append(
            {
                "identificador": m.get("identificador"),
                "mensaje": m.get("mensaje"),
                "informacion_adicional": m.get("informacionAdicional") or m.get("informacion_adicional"),
                "tipo": m.get("tipo"),
            }
        )
    return result


def _parse_xml_dict(element):
    children = list(element)
    if not children:
        text = (element.text or "").strip()
        return text
    result = {}
    for child in children:
        key = _strip_ns(child.tag)
        value = _parse_xml_dict(child)
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value
    return result


RETRYABLE_HTTP = {500, 502, 503, 504}


def humanize_sri_transport_error(detail: str) -> str:
    if "SRI HTTP 500" in detail and (
        "GenericJDBCException" in detail or "PersistenceException" in detail
    ):
        return (
            "El servidor del SRI (recepción) respondió con error interno (HTTP 500). "
            "No es un rechazo de validación de la factura: suele ser fallo temporal del SRI en pruebas "
            "o un reintento con la misma clave de acceso. Consulte autorización en el SRI; "
            "si no aparece, espere 2–5 minutos, use «Regenerar clave de acceso» y vuelva a emitir."
        )
    if "SRI HTTP 5" in detail:
        return (
            f"Error de comunicación con el SRI: {detail[:180]}. "
            "Reintente en unos minutos o consulte si el comprobante ya fue recibido."
        )
    return detail


def _post_soap(url: str, envelope: str) -> str:
    req = urllib.request.Request(
        url,
        data=envelope.encode("utf-8"),
        headers={"Content-Type": "text/xml;charset=UTF-8", "SOAPAction": ""},
        method="POST",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"SRI HTTP {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Error de conexión con el SRI: {exc.reason}") from exc


def _enviar_comprobante_once(signed_xml: str, ambiente: str, tipo_emision: str | None = "NORMAL") -> dict:
    url = get_sri_url("recepcion", ambiente, tipo_emision)
    xml_b64 = base64.b64encode(signed_xml.encode("utf-8")).decode("ascii")
    envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="{SRI_NS['recepcion']}">
  <soap:Body>
    <ec:validarComprobante>
      <xml>{xml_b64}</xml>
    </ec:validarComprobante>
  </soap:Body>
</soap:Envelope>"""
    text = _post_soap(url, envelope)
    root = ET.fromstring(text)
    resp = _find_first(root, "RespuestaRecepcionComprobante")
    if resp is None:
        raise RuntimeError("Respuesta inválida del SRI (recepción)")
    parsed = _parse_xml_dict(resp)
    estado = str(parsed.get("estado", "DESCONOCIDO"))
    mensajes = []
    comp = parsed.get("comprobantes", {})
    if isinstance(comp, dict):
        comp_item = comp.get("comprobante", comp)
        if isinstance(comp_item, dict):
            msgs = comp_item.get("mensajes", {})
            if isinstance(msgs, dict):
                mensajes = _normalize_mensajes(msgs.get("mensaje"))
    if not mensajes and isinstance(parsed.get("mensajes"), dict):
        mensajes = _normalize_mensajes(parsed["mensajes"].get("mensaje"))
    return {"estado": estado, "mensajes": mensajes}


def enviar_comprobante(
    signed_xml: str,
    ambiente: str,
    tipo_emision: str | None = "NORMAL",
    retries: int = 3,
    delay: float = 3.0,
) -> dict:
    """Como FactuSRI: un intento por llamada; reintenta solo errores HTTP 5xx del SRI."""
    last_exc = None
    for attempt in range(retries):
        try:
            return _enviar_comprobante_once(signed_xml, ambiente, tipo_emision)
        except RuntimeError as exc:
            last_exc = exc
            msg = str(exc)
            match = re.search(r"SRI HTTP (\d+)", msg)
            code = int(match.group(1)) if match else 0
            if code in RETRYABLE_HTTP and attempt < retries - 1:
                time.sleep(delay)
                continue
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("No se pudo enviar al SRI")


def consultar_autorizacion(clave_acceso: str, ambiente: str, tipo_emision: str | None = "NORMAL") -> dict:
    url = get_sri_url("autorizacion", ambiente, tipo_emision)
    envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="{SRI_NS['autorizacion']}">
  <soap:Body>
    <ec:autorizacionComprobante>
      <claveAccesoComprobante>{clave_acceso}</claveAccesoComprobante>
    </ec:autorizacionComprobante>
  </soap:Body>
</soap:Envelope>"""
    text = _post_soap(url, envelope)
    root = ET.fromstring(text)
    resp = _find_first(root, "RespuestaAutorizacionComprobante")
    if resp is None:
        raise RuntimeError("Respuesta inválida del SRI (autorización)")
    parsed = _parse_xml_dict(resp)
    autorizaciones = parsed.get("autorizaciones", {})
    auth = autorizaciones.get("autorizacion") if isinstance(autorizaciones, dict) else None
    if isinstance(auth, list):
        auth = auth[0] if auth else None
    if not auth:
        return {"estado": "SIN_AUTORIZACION", "mensajes": []}

    comprobante_xml = auth.get("comprobante")
    if isinstance(comprobante_xml, dict):
        comprobante_xml = comprobante_xml.get("#text")

    mensajes = []
    if isinstance(auth.get("mensajes"), dict):
        mensajes = _normalize_mensajes(auth["mensajes"].get("mensaje"))

    return {
        "estado": str(auth.get("estado", "DESCONOCIDO")),
        "numero_autorizacion": auth.get("numeroAutorizacion"),
        "fecha_autorizacion": auth.get("fechaAutorizacion"),
        "comprobante_xml": comprobante_xml,
        "mensajes": mensajes,
    }


def format_sri_mensajes(mensajes, estado=None) -> str:
    parts = []
    if estado:
        parts.append(str(estado))
    for m in mensajes or []:
        msg = m.get("mensaje") or ""
        extra = m.get("informacion_adicional") or ""
        ident = m.get("identificador") or ""
        line = " — ".join(x for x in [ident, msg, extra] if x)
        if line:
            parts.append(line)
    return "; ".join(parts) if parts else "Sin detalle del SRI"
