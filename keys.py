"""Neutral musical-key notation.

Translates a Beatport key into Camelot and Open-Key codes. This is factual
alternate-encoding metadata (like writing the same key two ways), not
harmonic-mixing logic.
"""

from __future__ import annotations

import re

# (root pitch class, mode) -> Camelot code. Enharmonic flats are normalised to sharps.
_CAMELOT: dict[tuple[str, str], str] = {
    ("G#", "minor"): "1A", ("D#", "minor"): "2A", ("A#", "minor"): "3A",
    ("F", "minor"): "4A", ("C", "minor"): "5A", ("G", "minor"): "6A",
    ("D", "minor"): "7A", ("A", "minor"): "8A", ("E", "minor"): "9A",
    ("B", "minor"): "10A", ("F#", "minor"): "11A", ("C#", "minor"): "12A",
    ("B", "major"): "1B", ("F#", "major"): "2B", ("C#", "major"): "3B",
    ("G#", "major"): "4B", ("D#", "major"): "5B", ("A#", "major"): "6B",
    ("F", "major"): "7B", ("C", "major"): "8B", ("G", "major"): "9B",
    ("D", "major"): "10B", ("A", "major"): "11B", ("E", "major"): "12B",
}

_FLAT_TO_SHARP = {
    "DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#", "CB": "B", "FB": "E",
}

_KEY_RE = re.compile(r"^\s*([A-Ga-g])([#♯b♭]?)\s*(maj|min|major|minor)\b", re.IGNORECASE)


def _parse_key(name: str | None) -> tuple[str, str] | None:
    if not name:
        return None
    match = _KEY_RE.match(name)
    if not match:
        return None
    letter, accidental, mode_token = match.group(1).upper(), match.group(2), match.group(3)
    if accidental in ("b", "♭"):
        root = _FLAT_TO_SHARP.get(letter + "B", letter)
    elif accidental in ("#", "♯"):
        root = letter + "#"
    else:
        root = letter
    mode = "minor" if mode_token.lower().startswith("min") else "major"
    return (root, mode)


def to_camelot(name: str | None) -> str | None:
    parsed = _parse_key(name)
    return _CAMELOT.get(parsed) if parsed else None


def to_open_key(camelot: str | None) -> str | None:
    if not camelot:
        return None
    number, letter = int(camelot[:-1]), camelot[-1]
    open_number = ((number - 8) % 12) + 1
    return f"{open_number}{'m' if letter == 'A' else 'd'}"


def format_key(key_obj: dict | None) -> str | None:
    """Readable key with Camelot/Open-Key, preferring Beatport-native camelot fields."""
    if not key_obj:
        return None
    name = key_obj.get("name")
    number, letter = key_obj.get("camelot_number"), key_obj.get("camelot_letter")
    camelot = f"{number}{letter}" if number and letter else to_camelot(name)
    if not camelot:
        return name
    return f"{name} (Camelot {camelot}, Open Key {to_open_key(camelot)})"
