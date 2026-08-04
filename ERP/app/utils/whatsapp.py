"""Utilidades para abrir WhatsApp Web/App con mensaje prefabricado (wa.me)."""

from __future__ import annotations

import re
from urllib.parse import quote


def normalize_whatsapp_phone(phone: str | None, default_country: str = "593") -> str | None:
    """Devuelve solo dígitos en formato internacional, o None si no es usable."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None

    # Ecuador: 09XXXXXXXX -> 5939XXXXXXXX
    if digits.startswith("0") and len(digits) == 10:
        digits = default_country + digits[1:]
    elif len(digits) == 9 and digits.startswith("9"):
        digits = default_country + digits
    elif len(digits) < 8:
        return None

    return digits


def build_whatsapp_url(phone: str | None, message: str) -> str | None:
    normalized = normalize_whatsapp_phone(phone)
    if not normalized:
        return None
    return f"https://wa.me/{normalized}?text={quote(message)}"


def quotation_whatsapp_message(quotation, company_name: str = "nuestro negocio") -> str:
    client_name = ""
    if quotation.client and quotation.client.name:
        client_name = quotation.client.name.split()[0]
    total = float(quotation.total or 0)
    greeting = f"Hola {client_name}," if client_name else "Hola,"
    return (
        f"{greeting}\n\n"
        f"Te compartimos la cotización #{quotation.id} de {company_name}.\n"
        f"Total: ${total:.2f}\n"
        f"Estado: {(quotation.status or '').capitalize()}\n\n"
        f"¿Confirmamos para avanzar?"
    )
