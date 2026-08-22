"""Resuelve nombres de color (catálogo / cotización) a CSS para la bolita."""

from __future__ import annotations

import re

# Nombres comunes en español + inglés → hex
_COLOR_NAMES: dict[str, str] = {
    "rojo": "#ef4444",
    "roja": "#ef4444",
    "red": "#ef4444",
    "azul": "#3b82f6",
    "blue": "#3b82f6",
    "verde": "#22c55e",
    "green": "#22c55e",
    "amarillo": "#eab308",
    "amarilla": "#eab308",
    "yellow": "#eab308",
    "naranja": "#f97316",
    "orange": "#f97316",
    "rosa": "#ec4899",
    "rosado": "#ec4899",
    "rosada": "#ec4899",
    "pink": "#ec4899",
    "fucsia": "#d946ef",
    "magenta": "#d946ef",
    "morado": "#a855f7",
    "morada": "#a855f7",
    "purple": "#a855f7",
    "violeta": "#8b5cf6",
    "lila": "#c4b5fd",
    "negro": "#171717",
    "negra": "#171717",
    "black": "#171717",
    "blanco": "#f8fafc",
    "blanca": "#f8fafc",
    "white": "#f8fafc",
    "gris": "#9ca3af",
    "gray": "#9ca3af",
    "grey": "#9ca3af",
    "plateado": "#94a3b8",
    "plateada": "#94a3b8",
    "silver": "#94a3b8",
    "dorado": "#ca8a04",
    "dorada": "#ca8a04",
    "gold": "#ca8a04",
    "cafe": "#92400e",
    "café": "#92400e",
    "marron": "#78350f",
    "marrón": "#78350f",
    "brown": "#78350f",
    "celeste": "#38bdf8",
    "cyan": "#22d3ee",
    "turquesa": "#14b8a6",
    "beige": "#d6c6a8",
    "crema": "#f5f0e6",
    "coral": "#fb7185",
    "bordo": "#7f1d1d",
    "burdeos": "#7f1d1d",
    "vino": "#7f1d1d",
    "wine": "#7f1d1d",
    "salmon": "#fda4af",
    "salmón": "#fda4af",
    "azul claro": "#93c5fd",
    "azul oscuro": "#1e3a8a",
    "verde claro": "#86efac",
    "verde oscuro": "#14532d",
    "rojo claro": "#fca5a5",
    "rojo oscuro": "#991b1b",
    "transparente": "transparent",
    "transparent": "transparent",
    "sin color": "",
    "-": "",
}

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RGB_RE = re.compile(
    r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*[\d.]+)?\s*\)$",
    re.I,
)


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def color_to_css(value: str | None) -> str | None:
    """
    Devuelve un color CSS usable en style=background-color.
    None si no hay color / no se puede resolver.
    """
    raw = (value or "").strip()
    if not raw or raw in {"-", "—", "Sin color", "sin color"}:
        return None

    hex_match = _HEX_RE.match(raw)
    if hex_match:
        h = hex_match.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return f"#{h.lower()}"

    rgb_match = _RGB_RE.match(raw)
    if rgb_match:
        r, g, b = (min(255, int(x)) for x in rgb_match.groups())
        return f"rgb({r}, {g}, {b})"

    key = _normalize_name(raw)
    if key in _COLOR_NAMES:
        css = _COLOR_NAMES[key]
        return css or None

    # "Amarillo pastel" → probar primera palabra
    first = key.split(" ", 1)[0]
    if first in _COLOR_NAMES:
        css = _COLOR_NAMES[first]
        return css or None

    return None
