"""Text helpers for Garmin-friendly GPX output."""

from __future__ import annotations

from unidecode import unidecode


def to_english(text: str) -> str:
    """Transliterate non-ASCII characters (e.g. Vietnamese) to ASCII."""
    if not text:
        return text
    return unidecode(text).strip()


def normalize_description(text: str) -> str:
    """Keep at most one sentence for Garmin-friendly waypoint text."""
    cleaned = to_english(text)
    if not cleaned:
        return ""

    sentence = cleaned.split(".", 1)[0].strip()
    if sentence and not sentence.endswith("."):
        sentence += "."
    return sentence[:512]