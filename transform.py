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


def format_track_summary(track: dict) -> str:
    bits = [f"#{track.get('id')} — {_title(track)} · {_artist_names(track)}"]
    if track.get("bpm"):
        bits.append(f"{track['bpm']} BPM")
    key = format_key(track.get("key"))
    if key:
        bits.append(key)
    return " · ".join(bits)


def format_search_results(data: dict, type: str) -> str:
    # Beatport keys the result list by the search `type` (verified Task 5),
    # e.g. {"tracks": [...], "count": N, "page": "1/1035", ...}.
    items = data.get(type) or []
    if not items:
        return "No results."
    if type == "tracks":
        body = "\n".join(format_track_summary(t) for t in items)
    else:
        body = "\n".join(f"#{item.get('id')} — {item.get('name', '?')}" for item in items)
    footer = []
    if data.get("page"):
        footer.append(f"Page {data['page']}")
    if data.get("count") is not None:
        footer.append(f"{data['count']} results")
    if footer:
        body += "\n" + " · ".join(footer)
    return body


def _pagination_footer(data: dict) -> str | None:
    bits = []
    if data.get("page"):
        bits.append(f"Page {data['page']}")
    count = data.get("count")
    if count is not None:
        bits.append("10000+ results" if count == 10000 else f"{count} results")
    return " · ".join(bits) if bits else None


def format_track_list(data: dict) -> str:
    items = data.get("results") or []
    if not items:
        return "No tracks."
    body = "\n".join(format_track_summary(t) for t in items)
    footer = _pagination_footer(data)
    return body + ("\n" + footer if footer else "")


def format_genre_list(data: dict) -> str:
    items = data.get("results") or []
    if not items:
        return "No genres."
    return "\n".join(f"#{g.get('id')} — {g.get('name', '?')}" for g in items)


def format_release_summary(release: dict) -> str:
    bits = [f"#{release.get('id')} — {release.get('name', '?')} · {_artist_names(release)}"]
    if release.get("track_count"):
        bits.append(f"{release['track_count']} tracks")
    if release.get("publish_date"):
        bits.append(release["publish_date"])
    return " · ".join(bits)


def format_release_list(data: dict) -> str:
    items = data.get("results") or []
    if not items:
        return "No releases."
    body = "\n".join(format_release_summary(r) for r in items)
    footer = _pagination_footer(data)
    return body + ("\n" + footer if footer else "")


def _trim(text: str, limit: int = 280) -> str:
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


def format_artist(artist: dict) -> str:
    lines = [f"Artist #{artist.get('id')} — {artist.get('name', 'Unknown')}"]
    if artist.get("bio"):
        lines.append(_trim(artist["bio"]))
    if artist.get("website"):
        lines.append(f"Website: {artist['website']}")
    return "\n".join(lines)


def format_release(release: dict) -> str:
    rid = release.get("id")
    name = release.get("name", "Untitled")
    header = f'Release #{rid} — "{name}" by {_artist_names(release)}'
    lines = [header]
    facts = []
    label = (release.get("label") or {}).get("name")
    if label:
        facts.append(f"Label: {label}")
    if release.get("catalog_number"):
        facts.append(f"Cat: {release['catalog_number']}")
    if release.get("publish_date"):
        facts.append(f"Released: {release['publish_date']}")
    if release.get("track_count"):
        facts.append(f"{release['track_count']} tracks")
    if facts:
        lines.append(" · ".join(facts))
    return "\n".join(lines)


def format_label(label: dict) -> str:
    lines = [f"Label #{label.get('id')} — {label.get('name', 'Unknown')}"]
    if label.get("bio"):
        lines.append(_trim(label["bio"]))
    return "\n".join(lines)


def format_genre(genre: dict) -> str:
    line = f"Genre #{genre.get('id')} — {genre.get('name', 'Unknown')}"
    subs = [s.get("name", "") for s in (genre.get("sub_genres") or []) if s.get("name")]
    if subs:
        line += f" (sub-genres: {', '.join(subs)})"
    return line


def format_chart(chart: dict) -> str:
    lines = [f"Chart #{chart.get('id')} — {chart.get('name', 'Untitled')}"]
    facts = []
    artist = chart.get("artist")
    if isinstance(artist, dict) and artist.get("name"):
        facts.append(f"By: {artist['name']}")
    if chart.get("track_count"):
        facts.append(f"{chart['track_count']} tracks")
    if chart.get("publish_date"):
        facts.append(f"Published: {chart['publish_date']}")
    if facts:
        lines.append(" · ".join(facts))
    if chart.get("description"):
        lines.append(_trim(chart["description"], 200))
    return "\n".join(lines)
