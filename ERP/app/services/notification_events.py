"""
Plantillas centralizadas de mensajes de notificación del ERP.

Ningún módulo de negocio debe hardcodear textos de alerta;
todos salen de aquí para mantener un solo lugar de edición.
"""

from __future__ import annotations

from datetime import datetime


def _money(value) -> str:
    try:
        return f"${float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _dt(value: datetime | str | None = None) -> str:
    if value is None:
        value = datetime.now()
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    return str(value)


def quote_approved(
    *,
    client: str,
    quotation_id: int | str,
    total,
    user: str = "—",
) -> str:
    return (
        "✅ *Nueva cotización aprobada*\n\n"
        f"👤 Cliente: `{client}`\n"
        f"📄 Cotización: `#{quotation_id}`\n"
        f"💰 Valor: `{_money(total)}`\n"
        f"🙋 Usuario: `{user}`"
    )


def quote_cancelled(
    *,
    client: str,
    quotation_id: int | str,
    total,
    previous_status: str = "—",
    user: str = "—",
) -> str:
    return (
        "❌ *Cotización cancelada*\n\n"
        f"👤 Cliente: `{client}`\n"
        f"📄 Cotización: `#{quotation_id}`\n"
        f"💰 Valor: `{_money(total)}`\n"
        f"📌 Estado anterior: `{previous_status}`\n"
        f"🙋 Usuario: `{user}`"
    )


def quote_sent_to_billing(
    *,
    client: str,
    quotation_id: int | str,
    total,
    invoice_ref: str = "—",
    user: str = "—",
) -> str:
    return (
        "🧾 *Cotización enviada a facturar*\n\n"
        f"👤 Cliente: `{client}`\n"
        f"📄 Cotización: `#{quotation_id}`\n"
        f"🧾 Factura: `{invoice_ref}`\n"
        f"💰 Valor: `{_money(total)}`\n"
        f"🙋 Usuario: `{user}`"
    )


def order_delayed(
    *,
    client: str,
    order_id: int | str,
    days_late: int,
    status: str,
) -> str:
    return (
        "⚠️ *Pedido atrasado*\n\n"
        f"👤 Cliente: `{client}`\n"
        f"🏭 Pedido: `OP-{int(order_id):04d}`\n"
        f"📅 Días de atraso: `{abs(int(days_late))}`\n"
        f"📌 Estado: `{status}`"
    )


def order_delivered(
    *,
    client: str,
    order_id: int | str,
    delivered_at: datetime | str | None = None,
) -> str:
    return (
        "🚚 *Pedido entregado*\n\n"
        f"👤 Cliente: `{client}`\n"
        f"📦 Pedido: `{order_id}`\n"
        f"🕐 Hora: `{_dt(delivered_at)}`"
    )


def material_shortage(
    *,
    material: str,
    stock,
    min_stock,
) -> str:
    return (
        "📉 *Falta de materia prima*\n\n"
        f"🧱 Material: `{material}`\n"
        f"📦 Existencia: `{stock}`\n"
        f"🔻 Mínimo: `{min_stock}`"
    )


def invoice_authorized(
    *,
    client: str,
    invoice_ref: str,
    total,
) -> str:
    return (
        "📄 *Factura autorizada*\n\n"
        f"👤 Cliente: `{client}`\n"
        f"🧾 Factura: `{invoice_ref}`\n"
        f"💰 Valor: `{_money(total)}`"
    )


def invoice_paid(
    *,
    client: str,
    invoice_ref: str,
    amount,
) -> str:
    return (
        "💰 *Factura pagada*\n\n"
        f"👤 Cliente: `{client}`\n"
        f"🧾 Factura: `{invoice_ref}`\n"
        f"💵 Monto: `{_money(amount)}`"
    )


def system_error(
    *,
    module: str,
    detail: str,
    user: str = "—",
    when: datetime | str | None = None,
) -> str:
    detail_clean = (detail or "").strip()
    if len(detail_clean) > 500:
        detail_clean = detail_clean[:500] + "…"
    return (
        "🚨 *Error crítico*\n\n"
        f"🧩 Módulo: `{module}`\n"
        f"❌ Detalle: `{detail_clean}`\n"
        f"🙋 Usuario: `{user}`\n"
        f"🕐 Fecha: `{_dt(when)}`"
    )


def server_started(*, env: str = "development", when: datetime | str | None = None) -> str:
    return (
        "🟢 *ERP iniciado*\n\n"
        f"🖥️ Entorno: `{env}`\n"
        f"🕐 Fecha: `{_dt(when)}`\n"
        "El servidor está en línea."
    )
