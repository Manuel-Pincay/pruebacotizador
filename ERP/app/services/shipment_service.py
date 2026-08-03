"""Guías de envío: contexto de etiqueta, permisos y cotizaciones elegibles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.client import Client
from app.models.company_config import CompanyConfig
from app.models.quotation import Quotation
from app.models.shipment import Shipment
from app.services.production_order_service import PRODUCTION_STATUS_LABELS, normalize_status

# Roles con acceso al módulo de despacho / guías
SHIPMENT_ROLES = ["admin", "disenador", "ventas", "despacho", "transporte"]

DEFAULT_GUIDE_COLORS = {
    "accent": "#d6452a",
    "border": "#8a97a8",
    "muted": "#6b7785",
}


def _normalize_hex_color(value: str | None, fallback: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if len(raw) == 4 and all(c in "0123456789abcdefABCDEF#" for c in raw):
        # #RGB -> #RRGGBB
        raw = f"#{raw[1]*2}{raw[2]*2}{raw[3]*2}"
    if len(raw) == 7 and all(c in "0123456789abcdefABCDEF#" for c in raw):
        return raw.lower()
    return fallback


def get_guide_colors(config: CompanyConfig | None) -> dict[str, str]:
    return {
        "accent": _normalize_hex_color(
            getattr(config, "guide_accent_color", None) if config else None,
            DEFAULT_GUIDE_COLORS["accent"],
        ),
        "border": _normalize_hex_color(
            getattr(config, "guide_border_color", None) if config else None,
            DEFAULT_GUIDE_COLORS["border"],
        ),
        "muted": _normalize_hex_color(
            getattr(config, "guide_muted_color", None) if config else None,
            DEFAULT_GUIDE_COLORS["muted"],
        ),
    }

# Cotizaciones desde las que se puede generar o imprimir guía
GUIDE_QUOTATION_STATUSES = frozenset({
    "aprobada",
    "produccion",
    "enviada",
    "enviado",
    "entregada",
    "entregado",
})

QUOTATION_STATUS_LABELS = {
    "aprobada": "Aprobada",
    "produccion": "En producción",
    "enviada": "Enviada",
    "enviado": "Enviado",
    "entregada": "Entregada",
    "entregado": "Entregado",
}


def quotation_internal_status(quotation: Quotation) -> dict[str, str]:
    q_code = (quotation.status or "pendiente").lower().strip()
    q_label = QUOTATION_STATUS_LABELS.get(q_code, q_code.replace("_", " ").title())
    po = quotation.production_order
    if po and po.status:
        po_code = normalize_status(po.status)
        po_label = PRODUCTION_STATUS_LABELS.get(po_code, po_code)
    else:
        po_code = ""
        po_label = "Sin orden de producción"
    return {
        "quotation_status": q_code,
        "quotation_status_label": q_label,
        "production_status": po_code,
        "production_status_label": po_label,
    }


@dataclass
class LabelSender:
    name: str
    city: str
    region: str
    phone: str
    address: str
    show_name: bool


def get_sender_from_config(config: CompanyConfig | None) -> LabelSender:
    if not config:
        return LabelSender("", "Manta", "Ecuador", "", "", False)
    name = (config.guide_sender_name or "").strip()
    return LabelSender(
        name=name,
        city=(config.guide_sender_city or "Manta").strip(),
        region=(config.guide_sender_region or "Ecuador").strip(),
        phone=(config.guide_sender_phone or "").strip(),
        address=(config.guide_sender_address or "").strip(),
        show_name=bool(name),
    )


def quotation_can_have_guide(quotation: Quotation | None) -> bool:
    if not quotation:
        return False
    return (quotation.status or "").lower().strip() in GUIDE_QUOTATION_STATUSES


def get_latest_shipment(db: Session, quotation_id: int) -> Shipment | None:
    return (
        db.query(Shipment)
        .filter(Shipment.quotation_id == quotation_id)
        .order_by(Shipment.id.desc())
        .first()
    )


def build_label_context(
    *,
    shipment: Shipment | None,
    quotation: Quotation,
    client: Client | None,
    config: CompanyConfig | None,
    size: str = "a4",
) -> dict[str, Any]:
    """Arma datos para la plantilla de guía (con o sin registro Shipment)."""
    size_norm = "a5" if (size or "").lower() == "a5" else "a4"
    sender = get_sender_from_config(config)

    if shipment:
        guide_number = shipment.guide_number or f"G-{shipment.id:05d}"
        customer_name = shipment.customer_name or (client.name if client else "—")
        customer_phone = shipment.customer_phone or (client.phone if client else "")
        customer_id = shipment.customer_id_number or (client.ruc_ci if client else "")
        destination_city = shipment.destination_city or ""
        destination_address = shipment.destination_address or (client.address if client else "")
        carrier = shipment.carrier or ""
        boxes = shipment.boxes or 1
        notes = shipment.notes or ""
        created_at = shipment.created_at
        shipment_id = shipment.id
    else:
        guide_number = f"COT-{quotation.id:05d}"
        customer_name = client.name if client else "—"
        customer_phone = client.phone if client else ""
        customer_id = client.ruc_ci if client else ""
        destination_city = ""
        destination_address = client.address if client else ""
        carrier = ""
        boxes = 1
        notes = ""
        created_at = quotation.created_at
        shipment_id = None

    return {
        "guide_number": guide_number,
        "quotation_id": quotation.id,
        "shipment_id": shipment_id,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_id_number": customer_id,
        "destination_city": destination_city,
        "destination_address": destination_address,
        "carrier": carrier,
        "boxes": boxes,
        "notes": notes,
        "created_at": created_at,
        "sender": sender,
        "company_name": config.company_name if config else "",
        "company_logo": config.logo if config else None,
        "print_size": size_norm,
        "is_draft": shipment is None,
        "colors": get_guide_colors(config),
        **quotation_internal_status(quotation),
    }


def list_quotations_for_guides(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.query(Quotation)
        .options(
            joinedload(Quotation.client),
            joinedload(Quotation.production_order),
        )
        .filter(Quotation.status.in_(list(GUIDE_QUOTATION_STATUSES)))
        .order_by(Quotation.id.desc())
        .all()
    )
    result = []
    for q in rows:
        client = q.client
        shipment = get_latest_shipment(db, q.id)
        internal = quotation_internal_status(q)
        result.append({
            "id": q.id,
            "client_name": client.name if client else "—",
            "status": q.status,
            "has_guide": shipment is not None,
            "guide_number": shipment.guide_number if shipment else None,
            "shipment_id": shipment.id if shipment else None,
            **internal,
        })
    return result
