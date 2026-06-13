"""Async httpx client for the Beatport v4 catalog API.

Owns bearer auth and refresh-on-401. Endpoint methods return parsed JSON dicts;
HTTP problems are raised as BeatportError with a user-facing message.
"""

from __future__ import annotations

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
    return resp.json()


class BeatportClient:
    def __init__(self, store: TokenStore, http: httpx.AsyncClient | None = None) -> None:
        self._store = store
        self._http = http or httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._store.access_token}",
            "Accept": "application/json",
        }

    async def _refresh(self) -> None:
        data = await refresh_tokens(self._store.client_id, self._store.refresh_token or "")
        self._store.update(data["access_token"], data.get("refresh_token"))

    async def _request(self, path: str, params: dict | None = None) -> dict[str, Any]:
        clean = _clean_params(params)
        resp = await self._http.get(path, params=clean, headers=self._headers())
        if resp.status_code == 401:
            await self._refresh()
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
