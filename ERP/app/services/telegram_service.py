"""
Cliente Telegram Bot API.

Nunca propaga excepciones al ERP: si Telegram falla, solo se registra en log.
Soporta uno o varios destinatarios (chat IDs separados por coma).
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from app.config.settings import settings

logger = logging.getLogger("erp.telegram")

_TELEGRAM_API = "https://api.telegram.org"
_DEFAULT_TIMEOUT = 8.0


def parse_chat_ids(raw: str | None) -> list[str]:
    """Acepta un ID o varios separados por coma/espacio/punto y coma."""
    if not raw:
        return []
    parts: list[str] = []
    for chunk in str(raw).replace(";", ",").replace(" ", ",").split(","):
        value = chunk.strip()
        if value:
            parts.append(value)
    # Sin duplicados, preservando orden
    seen: set[str] = set()
    unique: list[str] = []
    for item in parts:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


class TelegramService:
    """Envío de mensajes a uno o varios chats vía Bot API."""

    def __init__(
        self,
        *,
        token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: Optional[bool] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.token = (token if token is not None else settings.telegram_bot_token or "").strip()
        raw_chat = chat_id if chat_id is not None else settings.telegram_chat_id
        self.chat_ids = parse_chat_ids(raw_chat)
        # Compatibilidad: primer chat como atributo singular
        self.chat_id = self.chat_ids[0] if self.chat_ids else ""
        self.enabled = (
            bool(enabled)
            if enabled is not None
            else bool(settings.enable_telegram)
        )
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Token activo; los chat IDs pueden venir de admins en BD o del .env."""
        return bool(self.enabled and self.token)

    def _send_to_chat(
        self,
        chat_id: str,
        text: str,
        *,
        parse_mode: Optional[str] = None,
    ) -> bool:
        url = f"{_TELEGRAM_API}/bot{self.token}/sendMessage"
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            if response.status_code >= 400:
                logger.error(
                    "Telegram HTTP %s (chat %s): %s",
                    response.status_code,
                    chat_id,
                    (response.text or "")[:300],
                )
                return False
            data = response.json() if response.content else {}
            if not data.get("ok", False):
                logger.error(
                    "Telegram API rechazó mensaje (chat %s): %s",
                    chat_id,
                    data,
                )
                return False
            return True
        except requests.Timeout:
            logger.error("Telegram timeout (chat %s).", chat_id)
            return False
        except requests.RequestException as exc:
            logger.error("Telegram error de red (chat %s): %s", chat_id, exc)
            return False
        except Exception as exc:  # noqa: BLE001 — nunca romper el ERP
            logger.exception("Telegram fallo inesperado (chat %s): %s", chat_id, exc)
            return False

    def send_message(
        self,
        text: str,
        *,
        parse_mode: Optional[str] = None,
        chat_ids: Optional[list[str]] = None,
    ) -> bool:
        """Envía a los chat IDs indicados o a los configurados en .env. True si al menos uno aceptó."""
        if not self.enabled or not self.token:
            logger.debug("Telegram deshabilitado o sin token; mensaje omitido.")
            return False
        if not (text or "").strip():
            return False

        targets = list(chat_ids) if chat_ids is not None else list(self.chat_ids)
        targets = [t.strip() for t in targets if t and str(t).strip()]
        if not targets:
            logger.debug("Telegram sin destinatarios; mensaje omitido.")
            return False

        any_ok = False
        for chat_id in targets:
            if self._send_to_chat(chat_id, text, parse_mode=parse_mode):
                any_ok = True
        return any_ok

    def send_markdown(
        self,
        text: str,
        *,
        chat_ids: Optional[list[str]] = None,
    ) -> bool:
        """Markdown legacy de Telegram (parse_mode=Markdown)."""
        return self.send_message(text, parse_mode="Markdown", chat_ids=chat_ids)

    def send_error(self, text: str) -> bool:
        return self.send_markdown(f"🚨 {text}" if not text.startswith("🚨") else text)

    def send_warning(self, text: str) -> bool:
        return self.send_markdown(f"⚠️ {text}" if not text.startswith("⚠️") else text)

    def send_success(self, text: str) -> bool:
        return self.send_markdown(f"✅ {text}" if not text.startswith("✅") else text)


_telegram_singleton: TelegramService | None = None


def get_telegram_service() -> TelegramService:
    """Instancia única reutilizable en toda la app."""
    global _telegram_singleton
    if _telegram_singleton is None:
        _telegram_singleton = TelegramService()
    return _telegram_singleton


def reset_telegram_service() -> None:
    """Solo para tests."""
    global _telegram_singleton
    _telegram_singleton = None
