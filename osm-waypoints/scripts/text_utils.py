"""Text helpers for Garmin-friendly GPX output."""

from __future__ import annotations

from unidecode import unidecode


def to_english(text: str) -> str:
    """Transliterate non-ASCII characters (e.g. Vietnamese) to ASCII."""
    if not text:
        return text
    return unidecode(text).strip()


BANNED_PREFIXES = (
    "walk ",
    "walk to ",
    "visit ",
    "visit the ",
    "turn ",
    "turn to ",
    "see ",
    "see the ",
    "go to ",
    "head to ",
    "stop at ",
    "hike to ",
    "climb to ",
)

MAX_DESCRIPTION_WORDS = 8


def normalize_description(text: str) -> str:
    """Normalize to a short noun phrase for Garmin waypoint text."""
    cleaned = to_english(text).strip().strip("\"'").rstrip(".!?")
    if not cleaned:
        return ""

    phrase = cleaned.split(".", 1)[0].split(";", 1)[0].strip()
    lowered = phrase.lower()
    for prefix in BANNED_PREFIXES:
        if lowered.startswith(prefix):
            phrase = phrase[len(prefix) :].strip()
            lowered = phrase.lower()

    words = phrase.split()
    if len(words) > MAX_DESCRIPTION_WORDS:
        phrase = " ".join(words[:MAX_DESCRIPTION_WORDS])

    return phrase[:128]