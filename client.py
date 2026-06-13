"""Async httpx client for the Beatport v4 catalog API.

Owns bearer auth and refresh-on-401. Endpoint methods return parsed JSON dicts;
HTTP problems are raised as BeatportError with a user-facing message.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from auth import TokenStore, refresh_tokens

BASE_URL = "https://api.beatport.com/v4/"  # trailing slash: relative paths keep /v4


class BeatportError(Exception):
    """A user-facing API error (auth, not-found, rate-limit, etc.)."""


def _clean_params(params: dict | None) -> dict | None:
    if not params:
        return None
    out: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if key == "per_page":
            value = max(1, min(int(value), 100))
        out[key] = value
    return out or None


def _handle(resp: httpx.Response) -> dict[str, Any]:
    if resp.status_code == 401:
        raise BeatportError("Authentication failed — refresh your token (`uv run beatport-auth`).")
    if resp.status_code == 404:
        raise BeatportError("Not found.")
    if resp.status_code == 429:
        retry = resp.headers.get("Retry-After", "a few")
        raise BeatportError(f"Rate limited — retry after {retry} seconds.")
    resp.raise_for_status()
    try:
        return resp.json()
    except ValueError as exc:  # non-JSON body on a 2xx (e.g. an HTML error page)
        raise BeatportError("Unexpected non-JSON response from Beatport.") from exc


class BeatportClient:
    def __init__(self, store: TokenStore, http: httpx.AsyncClient | None = None) -> None:
        self._store = store
        self._http = http or httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
        self._refresh_lock = asyncio.Lock()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._store.access_token}",
            "Accept": "application/json",
        }

    async def _refresh(self, used_token: str | None) -> None:
        # Serialise refreshes: if several requests 401 at once, only the first refreshes;
        # the rest see the already-updated token and skip the (rotation-sensitive) round-trip.
        async with self._refresh_lock:
            if self._store.access_token != used_token:
                return
            try:
                data = await refresh_tokens(self._store.client_id, self._store.refresh_token or "")
            except httpx.HTTPError as exc:
                raise BeatportError(
                    "Authentication failed — refresh your token (`uv run beatport-auth`)."
                ) from exc
            self._store.update(data["access_token"], data.get("refresh_token"))

    async def _request(self, path: str, params: dict | None = None) -> dict[str, Any]:
        clean = _clean_params(params)
        used_token = self._store.access_token
        resp = await self._http.get(path, params=clean, headers=self._headers())
        if resp.status_code == 401:
            await self._refresh(used_token)
            resp = await self._http.get(path, params=clean, headers=self._headers())
        return _handle(resp)

    # --- endpoint methods (Plan A slice) ---
    async def search(self, query: str, type: str = "tracks",
                     page: int = 1, per_page: int = 25) -> dict[str, Any]:
        return await self._request("catalog/search/", {
            "q": query, "type": type, "page": page, "per_page": per_page,
        })

    async def track(self, track_id: int) -> dict[str, Any]:
        return await self._request(f"catalog/tracks/{track_id}/")

    async def list_tracks(self, genre_id: int | None = None, artist_id: int | None = None,
                          label_id: int | None = None, bpm: int | None = None,
                          key_id: int | None = None, name: str | None = None,
                          ordering: str | None = None, page: int = 1,
                          per_page: int = 25) -> dict[str, Any]:
        return await self._request("catalog/tracks/", {
            "genre_id": genre_id, "artist_id": artist_id, "label_id": label_id,
            "bpm": bpm, "key_id": key_id, "name": name, "ordering": ordering,
            "page": page, "per_page": per_page,
        })

    async def genres(self, per_page: int = 100) -> dict[str, Any]:
        return await self._request("catalog/genres/", {"per_page": per_page})

    async def genre(self, genre_id: int) -> dict[str, Any]:
        return await self._request(f"catalog/genres/{genre_id}/")

    async def genre_tracks(self, genre_id: int, per_page: int = 25) -> dict[str, Any]:
        return await self._request(f"catalog/genres/{genre_id}/tracks/", {"per_page": per_page})

    async def artist(self, artist_id: int) -> dict[str, Any]:
        return await self._request(f"catalog/artists/{artist_id}/")

    async def artist_tracks(self, artist_id: int, per_page: int = 25) -> dict[str, Any]:
        return await self._request(f"catalog/artists/{artist_id}/tracks/", {"per_page": per_page})

    async def release(self, release_id: int) -> dict[str, Any]:
        return await self._request(f"catalog/releases/{release_id}/")

    async def release_tracks(self, release_id: int, per_page: int = 25) -> dict[str, Any]:
        return await self._request(f"catalog/releases/{release_id}/tracks/", {"per_page": per_page})

    async def label(self, label_id: int) -> dict[str, Any]:
        return await self._request(f"catalog/labels/{label_id}/")

    async def label_releases(self, label_id: int, per_page: int = 25) -> dict[str, Any]:
        return await self._request(f"catalog/labels/{label_id}/releases/", {"per_page": per_page})

    async def charts(self, per_page: int = 25) -> dict[str, Any]:
        return await self._request("catalog/charts/", {"per_page": per_page})

    async def chart(self, chart_id: int) -> dict[str, Any]:
        return await self._request(f"catalog/charts/{chart_id}/")

    async def chart_tracks(self, chart_id: int, per_page: int = 25) -> dict[str, Any]:
        return await self._request(f"catalog/charts/{chart_id}/tracks/", {"per_page": per_page})
