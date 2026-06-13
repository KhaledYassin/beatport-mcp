"""Beatport MCP server: FastMCP instance and read-only catalog tools."""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

import transform
from auth import TokenStore
from client import BeatportClient, BeatportError

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


def main() -> None:
    mcp.run(transport="stdio")
