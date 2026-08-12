"""
Fachada única de notificaciones del ERP.

Hoy despacha a Telegram; mañana puede sumar Email/WhatsApp/Discord
sin tocar la lógica de negocio (solo este módulo).

Destinatarios: administradores con Telegram activo en /users.
Fallback opcional: TELEGRAM_CHAT_ID del .env si no hay admins configurados
(excepto arranque del servidor, que es solo admin en BD).
"""

from __future__ import annotations

import logging
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from app.config.settings import settings
from app.services import notification_events as events
from app.services.telegram_service import get_telegram_service, parse_chat_ids

logger = logging.getLogger("erp.notifications")

# Anti-spam: clave → timestamp del último envío
_last_sent: dict[str, float] = {}
_ERROR_COOLDOWN_SEC = 120
_DELAYED_COOLDOWN_SEC = 3600 * 12  # 12 h por pedido
_MATERIAL_COOLDOWN_SEC = 3600 * 6
# Arranque: debounce en disco (sobrevive a --reload / reinicios rápidos)
_SERVER_STARTED_COOLDOWN_SEC = 600
_SERVER_STARTED_STAMP = Path(tempfile.gettempdir()) / "erp_notify_server_started.stamp"


def _should_send(key: str, cooldown_sec: float) -> bool:
    now = time.monotonic()
    last = _last_sent.get(key)
    if last is not None and (now - last) < cooldown_sec:
        return False
    _last_sent[key] = now
    return True


def _running_with_reload() -> bool:
    """True cuando uvicorn está en modo --reload (arranques por cada cambio de archivo)."""
    return "--reload" in sys.argv


def _server_started_allowed() -> bool:
    """Debounce en disco: evita spam al reiniciar o al recargar el worker."""
    try:
        if _SERVER_STARTED_STAMP.exists():
            age = time.time() - _SERVER_STARTED_STAMP.stat().st_mtime
            if age < _SERVER_STARTED_COOLDOWN_SEC:
                return False
        _SERVER_STARTED_STAMP.write_text(str(time.time()), encoding="utf-8")
        return True
    except OSError as exc:
        logger.debug("No se pudo usar stamp de arranque: %s", exc)
        return True


def resolve_admin_telegram_chat_ids(
    *,
    include_env_fallback: bool = True,
) -> list[str]:
    """Chat IDs de administradores activos con Telegram habilitado."""
    ids: list[str] = []
    try:
        from app.database import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        try:
            rows = (
                db.query(User.telegram_chat_id)
                .filter(
                    User.role == "admin",
                    User.active.is_(True),
                    User.telegram_notify.is_(True),
                    User.telegram_chat_id.isnot(None),
                    User.telegram_chat_id != "",
                )
                .all()
            )
            for (chat_id,) in rows:
                ids.extend(parse_chat_ids(chat_id))
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.exception("No se pudieron leer chat IDs de admin: %s", exc)

    if not ids and include_env_fallback:
        ids.extend(parse_chat_ids(settings.telegram_chat_id))

    # Únicos
    seen: set[str] = set()
    unique: list[str] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _dispatch_async(
    builder: Callable[[], str],
    *,
    spam_key: Optional[str] = None,
    cooldown_sec: float = 0,
    admin_only: bool = True,
    include_env_fallback: bool = True,
) -> None:
    """Construye y envía en un hilo daemon para no bloquear la request HTTP."""

    def _run() -> None:
        try:
            if spam_key and cooldown_sec > 0 and not _should_send(spam_key, cooldown_sec):
                logger.debug("Notificación omitida por anti-spam: %s", spam_key)
                return
            text = builder()
            if not text:
                return
            chat_ids = resolve_admin_telegram_chat_ids(
                include_env_fallback=include_env_fallback,
            )
            if not chat_ids:
                logger.debug("Sin destinatarios admin de Telegram; omitido.")
                return
            get_telegram_service().send_markdown(text, chat_ids=chat_ids)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Fallo al despachar notificación: %s", exc)

    try:
        threading.Thread(target=_run, name="erp-notify", daemon=True).start()
    except Exception as exc:  # noqa: BLE001
        logger.exception("No se pudo iniciar hilo de notificación: %s", exc)


class NotificationService:
    """API pública para el resto del ERP (destinatarios: admins con Telegram)."""

    @staticmethod
    def notify_quote_approved(
        *,
        client: str,
        quotation_id: int | str,
        total: Any,
        user: str = "—",
    ) -> None:
        _dispatch_async(
            lambda: events.quote_approved(
                client=client or "—",
                quotation_id=quotation_id,
                total=total,
                user=user or "—",
            ),
        )

    @staticmethod
    def notify_quote_cancelled(
        *,
        client: str,
        quotation_id: int | str,
        total: Any,
        previous_status: str = "—",
        user: str = "—",
    ) -> None:
        _dispatch_async(
            lambda: events.quote_cancelled(
                client=client or "—",
                quotation_id=quotation_id,
                total=total,
                previous_status=previous_status or "—",
                user=user or "—",
            ),
        )

    @staticmethod
    def notify_quote_sent_to_billing(
        *,
        client: str,
        quotation_id: int | str,
        total: Any,
        invoice_ref: str = "—",
        user: str = "—",
    ) -> None:
        _dispatch_async(
            lambda: events.quote_sent_to_billing(
                client=client or "—",
                quotation_id=quotation_id,
                total=total,
                invoice_ref=invoice_ref or "—",
                user=user or "—",
            ),
        )

    @staticmethod
    def notify_order_delayed(
        *,
        client: str,
        order_id: int | str,
        days_late: int,
        status: str,
    ) -> None:
        _dispatch_async(
            lambda: events.order_delayed(
                client=client or "—",
                order_id=order_id,
                days_late=days_late,
                status=status or "—",
            ),
            spam_key=f"delayed:{order_id}",
            cooldown_sec=_DELAYED_COOLDOWN_SEC,
        )

    @staticmethod
    def notify_order_delivered(
        *,
        client: str,
        order_id: int | str,
        delivered_at: datetime | str | None = None,
    ) -> None:
        _dispatch_async(
            lambda: events.order_delivered(
                client=client or "—",
                order_id=order_id,
                delivered_at=delivered_at,
            ),
        )

    @staticmethod
    def notify_order_status_changed(
        *,
        client: str,
        order_id: int | str,
        from_status: str,
        to_status: str,
        status_code: str = "",
        user: str = "—",
        quotation_id: int | str | None = None,
    ) -> None:
        _dispatch_async(
            lambda: events.order_status_changed(
                client=client or "—",
                order_id=order_id,
                from_status=from_status or "—",
                to_status=to_status or "—",
                status_code=status_code or "",
                user=user or "—",
                quotation_id=quotation_id,
            ),
        )

    @staticmethod
    def notify_material_shortage(
        *,
        material: str,
        stock: Any,
        min_stock: Any,
        material_id: int | str | None = None,
    ) -> None:
        key = f"material:{material_id or material}"
        _dispatch_async(
            lambda: events.material_shortage(
                material=material or "—",
                stock=stock,
                min_stock=min_stock,
            ),
            spam_key=key,
            cooldown_sec=_MATERIAL_COOLDOWN_SEC,
        )

    @staticmethod
    def notify_invoice_authorized(
        *,
        client: str,
        invoice_ref: str,
        total: Any,
    ) -> None:
        _dispatch_async(
            lambda: events.invoice_authorized(
                client=client or "—",
                invoice_ref=invoice_ref,
                total=total,
            ),
        )

    @staticmethod
    def notify_invoice_paid(
        *,
        client: str,
        invoice_ref: str,
        amount: Any,
    ) -> None:
        _dispatch_async(
            lambda: events.invoice_paid(
                client=client or "—",
                invoice_ref=invoice_ref,
                amount=amount,
            ),
        )

    @staticmethod
    def notify_system_error(
        *,
        module: str,
        detail: str,
        user: str = "—",
        when: datetime | str | None = None,
    ) -> None:
        spam = f"error:{(module or '')[:80]}:{(detail or '')[:120]}"
        _dispatch_async(
            lambda: events.system_error(
                module=module or "ERP",
                detail=detail or "Error desconocido",
                user=user or "—",
                when=when,
            ),
            spam_key=spam,
            cooldown_sec=_ERROR_COOLDOWN_SEC,
        )

    @staticmethod
    def notify_server_started() -> None:
        """Aviso de arranque: solo admins con Telegram en BD (sin fallback .env).

        En desarrollo con uvicorn --reload no se envía (cada guardado reinicia el worker).
        Además hay cooldown en disco (~10 min) por si hay reinicios reales seguidos.
        """
        if _running_with_reload():
            logger.debug("Aviso de arranque omitido (uvicorn --reload).")
            return
        if not _server_started_allowed():
            logger.debug("Aviso de arranque omitido por cooldown.")
            return
        _dispatch_async(
            lambda: events.server_started(env=settings.app_env),
            admin_only=True,
            include_env_fallback=False,
        )

    @staticmethod
    def scan_delayed_orders(db) -> None:
        """Revisa OPs atrasadas y notifica (con anti-spam). Seguro llamar en cada visita a producción."""
        try:
            from app.models.production_order import ProductionOrder
            from app.services.production_helpers import (
                COMPLETED_ORDER_STATUSES,
                production_order_delivery_meta,
                production_orders_base_query,
            )
            from app.services.production_order_service import (
                PRODUCTION_STATUS_LABELS,
                normalize_status,
            )

            orders = (
                production_orders_base_query(db)
                .filter(ProductionOrder.status.notin_(list(COMPLETED_ORDER_STATUSES)))
                .all()
            )
            for order in orders:
                meta = production_order_delivery_meta(order)
                if not meta.get("is_overdue"):
                    continue
                days = meta.get("days_until")
                if days is None:
                    continue
                client_name = "—"
                if order.quotation and order.quotation.client:
                    client_name = order.quotation.client.name or "—"
                status_code = normalize_status(order.status)
                NotificationService.notify_order_delayed(
                    client=client_name,
                    order_id=order.id,
                    days_late=abs(int(days)),
                    status=PRODUCTION_STATUS_LABELS.get(status_code, status_code),
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("scan_delayed_orders falló: %s", exc)


def reset_notification_spam_cache() -> None:
    """Solo para tests."""
    _last_sent.clear()
    try:
        _SERVER_STARTED_STAMP.unlink(missing_ok=True)
    except OSError:
        pass
