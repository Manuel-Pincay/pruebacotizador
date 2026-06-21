"""Opciones de logo en ítems de cotización."""

from __future__ import annotations

LOGO_TYPE_SIN = "sin_logo"
LOGO_TYPE_CON = "con_logo"
LOGO_TYPE_GRABADO = "grabado"
LOGO_TYPE_IMPRESO = "impreso"

LOGO_TYPE_CHOICES: list[tuple[str, str]] = [
    (LOGO_TYPE_SIN, "Sin Logo"),
    (LOGO_TYPE_CON, "Con logo"),
    (LOGO_TYPE_GRABADO, "Con logo Grabado"),
    (LOGO_TYPE_IMPRESO, "Con logo impreso"),
]

LOGO_TYPE_LABELS = dict(LOGO_TYPE_CHOICES)
LOGO_TYPE_PDF_LABELS = {
    LOGO_TYPE_SIN: "S/L",
    LOGO_TYPE_CON: "C/Logo",
    LOGO_TYPE_GRABADO: "Grabado",
    LOGO_TYPE_IMPRESO: "Impreso",
}
VALID_LOGO_TYPES = frozenset(LOGO_TYPE_LABELS)


def normalize_logo_type(value) -> str:
    if value is None or value is False or value == "":
        return LOGO_TYPE_SIN
    if value is True or value in {1, "1", "true", "True", "yes", "on"}:
        return LOGO_TYPE_GRABADO
    text = str(value).strip().lower()
    if text in VALID_LOGO_TYPES:
        return text
    if text in {"si", "sí", "s", "yes", "con logo", "con_logo"}:
        return LOGO_TYPE_CON
    return LOGO_TYPE_SIN


def logo_type_label(value) -> str:
    return LOGO_TYPE_LABELS.get(normalize_logo_type(value), "Sin Logo")


def logo_type_pdf_label(value) -> str:
    return LOGO_TYPE_PDF_LABELS.get(normalize_logo_type(value), "S/L")


def resolve_item_logo_type(item) -> str:
    logo_type = getattr(item, "logo_type", None)
    if logo_type:
        return normalize_logo_type(logo_type)
    legacy_logo = getattr(item, "logo", None)
    if legacy_logo in (True, 1):
        return LOGO_TYPE_GRABADO
    return LOGO_TYPE_SIN


def register_logo_template_globals(env) -> None:
    env.globals["LOGO_TYPE_CHOICES"] = LOGO_TYPE_CHOICES
    env.globals["logo_type_label"] = logo_type_label
    env.globals["resolve_item_logo_type"] = resolve_item_logo_type
