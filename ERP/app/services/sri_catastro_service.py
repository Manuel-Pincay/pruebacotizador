"""Consulta de contribuyentes en el catastro público del SRI."""
from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.utils.sri_constants import CONSUMIDOR_FINAL, inferir_tipo_identificacion

logger = logging.getLogger("erp.sri_catastro")

SRI_CATASTRO_BASE = (
    "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest"
)


def normalizar_identificacion(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def ruc_para_consulta(identificacion: str) -> str | None:
    identificacion = normalizar_identificacion(identificacion)
    if len(identificacion) == 13 and identificacion.isdigit():
        return identificacion
    if len(identificacion) == 10 and identificacion.isdigit():
        return f"{identificacion}001"
    return None


def _fetch_json(url: str) -> Any | None:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ERP-Facturacion/1.0",
        },
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=12, context=context) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Consulta SRI fallida (%s): %s", url, exc)
        return None


def _first_item(data: Any) -> dict | None:
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        value = data.get("value")
        if isinstance(value, list) and value:
            return value[0]
    return None


def consultar_contribuyente(ruc_consulta: str) -> dict | None:
    url = (
        f"{SRI_CATASTRO_BASE}/ConsolidadoContribuyente/obtenerPorNumerosRuc"
        f"?&ruc={urllib.parse.quote(ruc_consulta)}"
    )
    data = _fetch_json(url)
    item = _first_item(data)
    if not item:
        return None
    return {
        "numero_ruc": item.get("numeroRuc") or ruc_consulta,
        "razon_social": (item.get("razonSocial") or "").strip(),
        "estado_contribuyente": item.get("estadoContribuyenteRuc"),
    }


def consultar_direccion_matriz(ruc_consulta: str) -> str | None:
    url = (
        f"{SRI_CATASTRO_BASE}/Establecimiento/consultarPorNumeroRuc"
        f"?numeroRuc={urllib.parse.quote(ruc_consulta)}"
    )
    data = _fetch_json(url)
    items: list = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("value"), list):
        items = data["value"]

    matriz = next((i for i in items if i.get("matriz") == "SI"), None)
    target = matriz or (items[0] if items else None)
    if not target:
        return None
    return (target.get("direccionCompleta") or "").strip() or None
