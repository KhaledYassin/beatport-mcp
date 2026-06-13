"""Pure formatters: raw Beatport JSON -> readable, LLM-friendly text.

No I/O. Each item leads with its ID so the model can chain follow-up calls.
Formatters tolerate missing fields.
"""

from __future__ import annotations

from keys import format_key


def _artist_names(obj: dict) -> str:
    names = [a.get("name", "") for a in (obj.get("artists") or []) if a.get("name")]
    return ", ".join(names) or "Unknown artist"


def _title(track: dict) -> str:
    name = track.get("name", "Untitled")
    mix = track.get("mix_name")
    return f"{name} ({mix})" if mix and mix != "Original Mix" else name


def format_track(track: dict) -> str:
    lines = [f'Track #{track.get("id")} — "{_title(track)}" by {_artist_names(track)}']

    facts: list[str] = []
    genre = (track.get("genre") or {}).get("name")
    if genre:
        facts.append(f"Genre: {genre}")
    if track.get("bpm"):
        facts.append(f"BPM: {track['bpm']}")
    key = format_key(track.get("key"))
    if key:
        facts.append(f"Key: {key}")
    if track.get("length"):
        facts.append(f"Length: {track['length']}")
    if facts:
        lines.append(" · ".join(facts))

    release = track.get("release") or {}
    rel: list[str] = []
    label = (release.get("label") or {}).get("name")
    if label:
        rel.append(f"Label: {label}")
    if release.get("name"):
        date = track.get("publish_date")  # publish_date is top-level on the track (Task 5)
        rel.append(f"Release: {release['name']}" + (f" ({date})" if date else ""))
    if rel:
        lines.append(" · ".join(rel))

    if track.get("sample_url"):
        lines.append(f"Preview: {track['sample_url']}")
    return "\n".join(lines)
