"""Estados visibles al cliente de tienda (pedido + pago)."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.quotation import Quotation
from app.services.production_order_service import normalize_status

STORE_ORDER_STEPS: list[tuple[str, str]] = [
    ("receptado", "Receptado"),
    ("fabricacion", "En fabricación"),
    ("enviado", "Enviado"),
    ("entregado", "Entregado"),
]

STORE_ORDER_LABELS = {
    **dict(STORE_ORDER_STEPS),
    "cancelado": "Cancelado",
}

# Sin comprobante de transferencia → cancelación automática
STORE_RECEIPT_DEADLINE_DAYS = 3


def new_store_access_token() -> str:
    return secrets.token_urlsafe(32)


def store_order_is_cancelled(quotation: Quotation) -> bool:
    st = (quotation.status or "").lower().strip()
    return st in {"cancelada", "cancelado", "vencida"}


def quotation_has_transfer_receipt(quotation: Quotation) -> bool:
    return any(
        (getattr(p, "transfer_receipt", None) or "").strip()
        for p in (quotation.payments or [])
    )


def store_receipt_deadline_at(quotation: Quotation) -> datetime | None:
    created = getattr(quotation, "created_at", None)
    if not created:
        return None
    return created + timedelta(days=STORE_RECEIPT_DEADLINE_DAYS)


def store_receipt_days_left(quotation: Quotation, *, now: datetime | None = None) -> int | None:
    """Días restantes para subir comprobante (None si ya no aplica)."""
    if store_order_is_cancelled(quotation):
        return None
    if quotation_has_transfer_receipt(quotation):
        return None
    if float(getattr(quotation, "total_paid", 0) or 0) > 0.009:
        return None
    deadline = store_receipt_deadline_at(quotation)
    if not deadline:
        return None
    now = now or datetime.utcnow()
    remaining = deadline - now
    if remaining.total_seconds() <= 0:
        return 0
    # redondeo hacia arriba en días calendario parciales
    return max(0, remaining.days + (1 if remaining.seconds or remaining.microseconds else 0))


def maybe_auto_cancel_store_order(db: Session, quotation: Quotation) -> bool:
    """
    Cancela cotizaciones de tienda sin comprobante tras STORE_RECEIPT_DEADLINE_DAYS.
    Devuelve True si acaba de cancelarla.
    """
    if (getattr(quotation, "source", None) or "") != "store":
        return False
    if store_order_is_cancelled(quotation):
        return False

    st = (quotation.status or "").lower().strip()
    if st in {"entregada", "entregado"}:
        return False
    if getattr(quotation, "electronic_invoice", None):
        return False
    if quotation_has_transfer_receipt(quotation):
        return False
    if float(getattr(quotation, "total_paid", 0) or 0) > 0.009:
        return False

    deadline = store_receipt_deadline_at(quotation)
    if not deadline or datetime.utcnow() < deadline:
        return False

    previous = st or "pendiente"
    quotation.status = "cancelada"

    try:
        from app.services.production_order_service import (
            get_production_order_by_quotation,
            log_history,
        )

        order = get_production_order_by_quotation(db, quotation.id)
        if order and normalize_status(order.status) != "cancelado":
            order.status = "cancelado"
            log_history(
                db,
                order,
                status="cancelado",
                notes=(
                    f"Cancelada automáticamente: sin comprobante en "
                    f"{STORE_RECEIPT_DEADLINE_DAYS} días (antes: {previous})."
                ),
                user_id=None,
            )
    except Exception:
        pass

    db.flush()

    try:
        from app.utils.quotation_events import log_quotation_event

        log_quotation_event(
            db,
            quotation.id,
            "cancelada",
            (
                f"Cancelada automáticamente: sin comprobante de transferencia "
                f"en {STORE_RECEIPT_DEADLINE_DAYS} días (antes: {previous})"
            ),
            None,
        )
    except Exception:
        pass

    try:
        from app.utils.activity import log_activity

        log_activity(
            db,
            "Cotización cancelada (tienda)",
            f"#{quotation.id}: sin comprobante en {STORE_RECEIPT_DEADLINE_DAYS} días",
        )
    except Exception:
        pass

    db.commit()
    db.refresh(quotation)
    return True


def store_order_status_code(quotation: Quotation) -> str:
    """receptado | fabricacion | enviado | entregado | cancelado"""
    if store_order_is_cancelled(quotation):
        return "cancelado"

    qst = (quotation.status or "").lower().strip()
    po = getattr(quotation, "production_order", None)
    po_st = normalize_status(po.status) if po else None

    if qst in {"entregada", "entregado"} or po_st == "entregado":
        return "entregado"
    if qst in {"enviada", "enviado"} or po_st == "envio":
        return "enviado"
    if qst == "produccion" or po_st == "produccion":
        return "fabricacion"
    # pendiente / aprobada / diseño / sin OP → receptado
    return "receptado"


def store_order_timeline(quotation: Quotation) -> list[dict]:
    if store_order_is_cancelled(quotation):
        return [
            {
                "code": "cancelado",
                "label": "Cancelado",
                "state": "cancelled",
            }
        ]

    current = store_order_status_code(quotation)
    codes = [c for c, _ in STORE_ORDER_STEPS]
    idx = codes.index(current) if current in codes else 0
    steps = []
    for i, (code, label) in enumerate(STORE_ORDER_STEPS):
        if i < idx:
            state = "done"
        elif i == idx:
            state = "current"
        else:
            state = "todo"
        steps.append({"code": code, "label": label, "state": state})
    return steps


def store_payment_summary(quotation: Quotation) -> dict:
    """Resumen de pago para la vista del cliente."""
    cancelled = store_order_is_cancelled(quotation)
    pending_rows = [
        p
        for p in (quotation.payments or [])
        if (getattr(p, "verification_status", None) or "") == "pending"
    ]
    rejected_rows = [
        p
        for p in (quotation.payments or [])
        if (getattr(p, "verification_status", None) or "") == "rejected"
    ]

    if cancelled:
        code = "cancelled"
        label = "Pedido cancelado"
    elif quotation.payment_status == "pagada":
        code = "confirmed"
        label = "Pago confirmado"
    elif pending_rows:
        code = "waiting"
        label = "Esperando verificación"
    elif quotation.payment_status == "parcial":
        code = "partial"
        label = "Pago parcial confirmado"
    elif rejected_rows and quotation.total_paid <= 0:
        code = "rejected"
        label = "Pago rechazado — puedes subir otro comprobante"
    else:
        code = "unpaid"
        label = "Pendiente de pago"

    days_left = store_receipt_days_left(quotation)
    can_upload = (
        not cancelled
        and quotation.open_balance_for_new_payment > 0.009
    )

    return {
        "code": code,
        "label": label,
        "total": float(quotation.total or 0),
        "total_paid": float(quotation.total_paid or 0),
        "pending_verification": float(quotation.amount_pending_verification or 0),
        "open_balance": float(quotation.open_balance_for_new_payment or 0),
        "can_upload": can_upload,
        "cancelled": cancelled,
        "receipt_deadline_days": STORE_RECEIPT_DEADLINE_DAYS,
        "receipt_days_left": days_left,
        "has_receipt": quotation_has_transfer_receipt(quotation),
    }
