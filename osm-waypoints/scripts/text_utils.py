"""Text helpers for Garmin-friendly GPX output."""

from __future__ import annotations

from unidecode import unidecode


def to_english(text: str) -> str:
    """Transliterate non-ASCII characters (e.g. Vietnamese) to ASCII."""
    if not text:
        return text
    return unidecode(text).strip()