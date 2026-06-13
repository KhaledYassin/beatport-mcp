"""Beatport MCP server: FastMCP instance and read-only catalog tools."""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

import transform
from auth import TokenStore
from client import BeatportClient, BeatportError
from keys import key_name_to_id

mcp = FastMCP("beatport")

_client: BeatportClient | None = None


def _get_client() -> BeatportClient:
    global _client
    if _client is None:
        _client = BeatportClient(TokenStore.from_env())
    return _client


@mcp.tool()
async def get_track(track_id: int) -> str:
    """Get full details for a Beatport track by its numeric ID: title, artists, BPM,
    musical key (with Camelot/Open-Key), genre, length, label, release, and preview URL."""
    try:
        data = await _get_client().track(track_id)
    except (BeatportError, httpx.HTTPError) as exc:
        return f"Error: {exc}"
    return transform.format_track(data)


@mcp.tool()
async def search(query: str, type: str = "tracks", page: int = 1, per_page: int = 25) -> str:
    """Search the Beatport catalog. `type` is one of: tracks, artists, releases, labels,
    charts. Returns a compact list; each line starts with the item's ID for follow-up calls."""
    try:
        data = await _get_client().search(query, type=type, page=page, per_page=per_page)
    except (BeatportError, httpx.HTTPError) as exc:
        return f"Error: {exc}"
    return transform.format_search_results(data, type)


@mcp.tool()
async def list_tracks(genre_id: int | None = None, artist_id: int | None = None,
                      label_id: int | None = None, bpm: int | None = None,
                      key: str | None = None, name: str | None = None,
                      newest_first: bool = True, page: int = 1, per_page: int = 25) -> str:
    """Browse/filter catalog tracks. Filters: genre_id, artist_id, label_id, exact bpm,
    key (a musical key name like "A minor" — resolved to Beatport's key), and name (substring).
    Results sort by release date (newest first unless newest_first=False). NOTE: the API supports
    only an EXACT bpm, not a range — call multiple bpm values to cover a range."""
    key_id = None
    if key is not None:
        key_id = key_name_to_id(key)
        if key_id is None:
            return (
                f"Error: unrecognised musical key '{key}'."
                " Use a form like 'A minor' or 'F# major'."
            )
    ordering = "-publish_date" if newest_first else "publish_date"
    try:
        data = await _get_client().list_tracks(
            genre_id=genre_id, artist_id=artist_id, label_id=label_id, bpm=bpm,
            key_id=key_id, name=name, ordering=ordering, page=page, per_page=per_page)
    except (BeatportError, httpx.HTTPError) as exc:
        return f"Error: {exc}"
    return transform.format_track_list(data)


@mcp.tool()
async def list_genres() -> str:
    """List all Beatport genres with their IDs
    (use an ID to filter list_tracks or call get_genre)."""
    try:
        data = await _get_client().genres()
    except (BeatportError, httpx.HTTPError) as exc:
        return f"Error: {exc}"
    return transform.format_genre_list(data)


@mcp.tool()
async def get_artist(artist_id: int) -> str:
    """Get an artist by ID: profile plus their most recent tracks."""
    try:
        client = _get_client()
        detail = await client.artist(artist_id)
        tracks = await client.artist_tracks(artist_id, per_page=10)
    except (BeatportError, httpx.HTTPError) as exc:
        return f"Error: {exc}"
    return transform.format_artist(detail) + "\n\nTracks:\n" + transform.format_track_list(tracks)


@mcp.tool()
async def get_release(release_id: int) -> str:
    """Get a release (single/EP/album) by ID: details plus its full tracklist."""
    try:
        client = _get_client()
        detail = await client.release(release_id)
        tracks = await client.release_tracks(release_id, per_page=50)
    except (BeatportError, httpx.HTTPError) as exc:
        return f"Error: {exc}"
    return transform.format_release(detail) + "\n\nTracks:\n" + transform.format_track_list(tracks)


@mcp.tool()
async def get_label(label_id: int) -> str:
    """Get a label by ID: profile plus its most recent releases."""
    try:
        client = _get_client()
        detail = await client.label(label_id)
        releases = await client.label_releases(label_id, per_page=10)
    except (BeatportError, httpx.HTTPError) as exc:
        return f"Error: {exc}"
    releases_text = transform.format_release_list(releases)
    return transform.format_label(detail) + "\n\nReleases:\n" + releases_text


@mcp.tool()
async def get_genre(genre_id: int) -> str:
    """Get a genre by ID: details plus its most recent tracks."""
    try:
        client = _get_client()
        detail = await client.genre(genre_id)
        tracks = await client.genre_tracks(genre_id, per_page=10)
    except (BeatportError, httpx.HTTPError) as exc:
        return f"Error: {exc}"
    return transform.format_genre(detail) + "\n\nTracks:\n" + transform.format_track_list(tracks)


@mcp.tool()
async def get_chart(chart_id: int) -> str:
    """Get a chart (curated track list) by ID: details plus its tracks."""
    try:
        client = _get_client()
        detail = await client.chart(chart_id)
        tracks = await client.chart_tracks(chart_id, per_page=50)
    except (BeatportError, httpx.HTTPError) as exc:
        return f"Error: {exc}"
    return transform.format_chart(detail) + "\n\nTracks:\n" + transform.format_track_list(tracks)


def main() -> None:
    mcp.run(transport="stdio")
