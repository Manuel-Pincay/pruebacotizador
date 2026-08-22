"""Normalización de texto ingresado por el usuario."""

from __future__ import annotations

import re

# Palabras que deben conservarse en mayúsculas (tallas, materiales, unidades).
UPPERCASE_WORDS = frozenset({
    "xl", "xxl", "xs", "xxs", "sm", "md", "lg",
    "mdf", "pvc", "cm", "mm", "sl",
})


def _title_word(word: str) -> str:
    if not word:
        return word

    key = word.casefold()
    if word.isalpha() and key in UPPERCASE_WORDS:
        return key.upper()

    if word.isalpha():
        return key[0].upper() + key[1:]

    for index, char in enumerate(word):
        if not char.isalpha():
            continue
        segment = word[index:]
        segment_key = segment.casefold()
        if segment.isalpha() and segment_key in UPPERCASE_WORDS:
            return word[:index] + segment_key.upper()
        return word[:index] + segment_key[0].upper() + segment_key[1:]

    return word


def format_title_words(value: str | None) -> str:
    """
    Convierte texto a formato oración por palabra.
    Ej: 'manuel pincay gonzalez' -> 'Manuel Pincay Gonzalez'
        'base dorada grande xl' -> 'Base Dorada Grande XL'
    """
    text = " ".join((value or "").split())
    if not text:
        return ""
    return " ".join(_title_word(word) for word in text.split())


def format_product_size(size: str | None, unit: str | None = None) -> str:
    """Normaliza medidas libres: '50 x 40', '50X40', '50×40 cm' -> '50x40' o '50x40 cm'."""
    text = " ".join((size or "").split())
    if not text:
        return ""

    text = re.sub(r"\s*[xX×]\s*", "x", text)
    unit_text = (unit or "").strip()
    if not unit_text:
        return text
    if text.lower().endswith(unit_text.lower()):
        return text
    return f"{text} {unit_text}".strip()
