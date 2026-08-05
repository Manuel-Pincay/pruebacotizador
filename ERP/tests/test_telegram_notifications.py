"""Tests del módulo de notificaciones Telegram (sin red real)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services import notification_events as events
from app.services.notification_service import (
    NotificationService,
    reset_notification_spam_cache,
)
from app.services.telegram_service import (
    TelegramService,
    reset_telegram_service,
)


@pytest.fixture(autouse=True)
def _reset_singletons():
    reset_telegram_service()
    reset_notification_spam_cache()
    yield
    reset_telegram_service()
    reset_notification_spam_cache()


def test_event_templates_contain_keywords():
    assert "aprobada" in events.quote_approved(
        client="ACME", quotation_id=1, total=100, user="ana"
    ).lower()
    assert "cancelada" in events.quote_cancelled(
        client="ACME", quotation_id=2, total=50, previous_status="pendiente", user="ana"
    ).lower()
    assert "facturar" in events.quote_sent_to_billing(
        client="ACME", quotation_id=3, total=80, invoice_ref="001-001-1", user="ana"
    ).lower()
    assert "atrasado" in events.order_delayed(
        client="ACME", order_id=2, days_late=3, status="Producción"
    ).lower()
    assert "entregado" in events.order_delivered(client="ACME", order_id="OP-0001").lower()
    assert "materia prima" in events.material_shortage(
        material="MDF", stock=1, min_stock=5
    ).lower()
    assert "autorizada" in events.invoice_authorized(
        client="ACME", invoice_ref="001-001-1", total=50
    ).lower()
    assert "pagada" in events.invoice_paid(
        client="ACME", invoice_ref="Cot #1", amount=50
    ).lower()
    assert "crítico" in events.system_error(module="x", detail="boom").lower()


def test_telegram_disabled_does_not_call_network():
    svc = TelegramService(token="", chat_id="", enabled=False)
    with patch("app.services.telegram_service.requests.post") as post:
        assert svc.send_message("hola") is False
        post.assert_not_called()


def test_telegram_send_success():
    svc = TelegramService(token="tok", chat_id="123", enabled=True, timeout=1)
    fake = MagicMock()
    fake.status_code = 200
    fake.content = b'{"ok": true}'
    fake.json.return_value = {"ok": True}
    with patch("app.services.telegram_service.requests.post", return_value=fake) as post:
        assert svc.send_markdown("hola *mundo*") is True
        post.assert_called_once()
        kwargs = post.call_args.kwargs
        assert kwargs["json"]["chat_id"] == "123"
        assert kwargs["json"]["parse_mode"] == "Markdown"


def test_telegram_sends_to_multiple_chats():
    from app.services.telegram_service import parse_chat_ids

    assert parse_chat_ids("111, 222;333") == ["111", "222", "333"]
    svc = TelegramService(token="tok", chat_id="111,222", enabled=True, timeout=1)
    fake = MagicMock()
    fake.status_code = 200
    fake.content = b'{"ok": true}'
    fake.json.return_value = {"ok": True}
    with patch("app.services.telegram_service.requests.post", return_value=fake) as post:
        assert svc.send_message("hola") is True
        assert post.call_count == 2
        chats = [c.kwargs["json"]["chat_id"] for c in post.call_args_list]
        assert chats == ["111", "222"]


def test_telegram_network_error_swallowed():
    svc = TelegramService(token="tok", chat_id="123", enabled=True, timeout=1)
    with patch(
        "app.services.telegram_service.requests.post",
        side_effect=Exception("down"),
    ):
        assert svc.send_message("x") is False


def test_notification_service_dispatches_async():
    with patch(
        "app.services.notification_service.resolve_admin_telegram_chat_ids",
        return_value=["111"],
    ), patch("app.services.notification_service.get_telegram_service") as get_tg:
        mock_tg = MagicMock()
        get_tg.return_value = mock_tg
        NotificationService.notify_quote_approved(
            client="C", quotation_id=9, total=10, user="u"
        )
        # Esperar hilo daemon
        import time

        time.sleep(0.3)
        mock_tg.send_markdown.assert_called_once()
        args, kwargs = mock_tg.send_markdown.call_args
        text = args[0]
        assert "aprobada" in text.lower()
        assert "#9" in text
        assert kwargs.get("chat_ids") == ["111"]


def test_notify_quote_cancelled_and_sent_to_billing():
    with patch(
        "app.services.notification_service.resolve_admin_telegram_chat_ids",
        return_value=["111"],
    ), patch("app.services.notification_service.get_telegram_service") as get_tg:
        mock_tg = MagicMock()
        get_tg.return_value = mock_tg
        NotificationService.notify_quote_cancelled(
            client="C", quotation_id=4, total=20, previous_status="aprobada", user="u"
        )
        NotificationService.notify_quote_sent_to_billing(
            client="C", quotation_id=5, total=30, invoice_ref="001-001-9", user="u"
        )
        import time

        time.sleep(0.4)
        assert mock_tg.send_markdown.call_count == 2
        texts = [c.args[0].lower() for c in mock_tg.send_markdown.call_args_list]
        assert any("cancelada" in t for t in texts)
        assert any("facturar" in t for t in texts)


def test_system_error_anti_spam():
    with patch(
        "app.services.notification_service.resolve_admin_telegram_chat_ids",
        return_value=["111"],
    ), patch("app.services.notification_service.get_telegram_service") as get_tg:
        mock_tg = MagicMock()
        get_tg.return_value = mock_tg
        NotificationService.notify_system_error(module="m", detail="same")
        NotificationService.notify_system_error(module="m", detail="same")
        import time

        time.sleep(0.4)
        assert mock_tg.send_markdown.call_count == 1


def test_server_started_uses_admin_only_without_env_fallback():
    with patch(
        "app.services.notification_service._running_with_reload",
        return_value=False,
    ), patch(
        "app.services.notification_service.resolve_admin_telegram_chat_ids",
        return_value=[],
    ) as resolve, patch(
        "app.services.notification_service.get_telegram_service"
    ) as get_tg:
        mock_tg = MagicMock()
        get_tg.return_value = mock_tg
        NotificationService.notify_server_started()
        import time

        time.sleep(0.3)
        resolve.assert_called()
        assert resolve.call_args.kwargs.get("include_env_fallback") is False
        mock_tg.send_markdown.assert_not_called()


def test_server_started_skipped_under_reload():
    with patch(
        "app.services.notification_service._running_with_reload",
        return_value=True,
    ), patch(
        "app.services.notification_service.resolve_admin_telegram_chat_ids",
    ) as resolve, patch(
        "app.services.notification_service.get_telegram_service"
    ) as get_tg:
        NotificationService.notify_server_started()
        import time

        time.sleep(0.2)
        resolve.assert_not_called()
        get_tg.assert_not_called()
