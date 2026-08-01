"""Correos del cliente: principal (SRI) y adicionales (solo envío ERP)."""
from __future__ import annotations

import json
import re

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(normalize_email(value)))


def parse_additional_emails_raw(raw: str | None) -> list[str]:
    """Acepta correos separados por coma, punto y coma o salto de línea."""
    if not raw or not str(raw).strip():
        return []
    parts = re.split(r"[,;\n\r]+", str(raw))
    result = []
    seen = set()
    for part in parts:
        email = normalize_email(part)
        if email and is_valid_email(email) and email not in seen:
            seen.add(email)
            result.append(email)
    return result


def load_additional_emails(client) -> list[str]:
    if not client or not getattr(client, "additional_emails_json", None):
        return []
    try:
        data = json.loads(client.additional_emails_json)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return parse_additional_emails_raw(",".join(str(x) for x in data))


def save_additional_emails(emails: list[str]) -> str | None:
    clean = parse_additional_emails_raw(",".join(emails))
    if not clean:
        return None
    return json.dumps(clean, ensure_ascii=False)


def additional_emails_display(client) -> str:
    return ", ".join(load_additional_emails(client))


def collect_client_recipients(client, extra: list[str] | None = None) -> list[str]:
    """Correo principal + adicionales guardados + extras puntuales (sin duplicados)."""
    recipients: list[str] = []
    seen: set[str] = set()
    primary = normalize_email(getattr(client, "email", None) or "")
    if primary and is_valid_email(primary):
        recipients.append(primary)
        seen.add(primary)
    for email in load_additional_emails(client):
        if email not in seen:
            recipients.append(email)
            seen.add(email)
    for email in parse_additional_emails_raw(",".join(extra or [])):
        if email not in seen:
            recipients.append(email)
            seen.add(email)
    return recipients
