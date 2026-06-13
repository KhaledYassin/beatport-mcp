# Beatport MCP — Foundation & Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take `beatport-mcp` from scaffold to a working, neutral, read-only catalog MCP server with two live tools (`search`, `get_track`), plus the auth/client/transform foundation the remaining tools build on.

**Architecture:** Approach A from the design spec — flat modules at repo root with one responsibility each: `auth` (token store + browser PKCE bootstrap), `client` (async httpx I/O + refresh-on-401), `keys` (neutral Camelot/Open-Key notation), `transform` (pure JSON→readable-text formatters), `server` (FastMCP tools). A live-verification step captures real fixtures and locks the gating contracts before the formatters/tools are finalized.

**Tech Stack:** Python 3.12, `mcp[cli]` (FastMCP), `httpx` (async), `uv`, `ruff`, `pyright`, `pytest` + `pytest-asyncio` + `respx`.

**Scope note:** This is Plan A. The other 7 catalog tools (`list_tracks`, `get_artist`, `get_release`, `get_label`, `list_genres`, `get_genre`, `get_chart`) are **Plan B**, written after Task 4 (live verification) confirms exact filter params, pagination envelope, and key-object shape. Reference spec: `docs/superpowers/specs/2026-06-13-beatport-mcp-catalog-design.md`.

**Branch:** all work on `feat/catalog-tools` (already created).

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | deps, build backend, `[project.scripts]`, tool configs |
| `auth.py` | `TokenStore` (state + file persistence), `refresh_tokens()` (async network), PKCE bootstrap `main()` |
| `client.py` | `BeatportClient` (async httpx, bearer, refresh-on-401, error mapping), endpoint methods |
| `keys.py` | neutral key-notation: `to_camelot`, `to_open_key`, `format_key` |
| `transform.py` | pure formatters: `format_track`, `format_track_summary`, `format_search_results` |
| `server.py` | `FastMCP` instance, `@mcp.tool()` defs, lazy client, `main()` |
| `main.py` | thin console-script entry → `server.main()` |
| `scripts/verify.py` | manual live-probe / fixture-capture (NOT in CI) |
| `tests/test_keys.py` | pure unit tests for key notation |
| `tests/test_auth.py` | `TokenStore` persistence + PKCE-helper + `refresh_tokens` (respx) |
| `tests/test_client.py` | request building, bearer, 401→refresh→retry, error mapping (respx) |
| `tests/test_transform.py` | formatter output against hand-authored fixtures |
| `tests/fixtures/` | captured/representative JSON |
| `.env.example` | documents required env vars (committed; no secrets) |
| `README.md` | corrected setup (valid JSON, real env vars, browser-login bootstrap) |

---

## Task 1: Project scaffolding & tooling

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Modify: `beatport.py` (delete — content moves to `server.py` later; remove weather boilerplate now)
- Create: `.env.example`

- [ ] **Step 1: Replace `pyproject.toml`**

```toml
[project]
name = "beatport-mcp"
version = "0.1.0"
description = "MCP server for the Beatport v4 catalog API."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "mcp[cli]>=1.5.0",
    "httpx>=0.28.1",
]

[project.scripts]
beatport-mcp = "main:main"
beatport-auth = "auth:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
include = ["main.py", "server.py", "client.py", "transform.py", "keys.py", "auth.py"]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "respx>=0.21.1",
    "ruff>=0.6.0",
    "pyright>=1.1.380",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pyright]
typeCheckingMode = "standard"
pythonVersion = "3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Note: `requests` is intentionally removed — `auth.py` now uses `httpx`.

- [ ] **Step 2: Fix `.gitignore` token line**

Replace the `soundcloud_token.json` line with the actual artifacts:

```
# token file
.beatport_token.json
.beatport-mcp/
```

(`.env` is already ignored. `.env.example` is NOT ignored — it stays committed.)

- [ ] **Step 3: Remove the weather boilerplate**

Delete `beatport.py` (its `FastMCP` init is re-created cleanly in `server.py` in Task 8; the `NWS_API_BASE` weather constant must not survive):

```bash
git rm beatport.py
```

- [ ] **Step 4: Create `.env.example`**

```
# Beatport OAuth credentials. Copy to .env and fill in (never commit .env).
# CLIENT_ID is in your browser devtools POST /auth/o/token/ payload (interim),
# or printed by `uv run beatport-auth` once the browser login is wired up.
CLIENT_ID=
ACCESS_TOKEN=
REFRESH_TOKEN=
# Optional: override where refreshed tokens are persisted.
# BEATPORT_TOKEN_PATH=~/.beatport-mcp/token.json
```

- [ ] **Step 5: Sync deps and confirm tooling runs**

Run: `uv sync && uv run ruff --version && uv run pyright --version && uv run pytest --version`
Expected: all four print versions; `uv sync` resolves with `mcp`, `httpx`, and the dev group (no `requests`).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore .env.example
git rm --cached beatport.py 2>/dev/null; git add -A
git commit -m "chore: project tooling, drop weather boilerplate and requests dep"
```

---

## Task 2: Neutral key-notation (`keys.py`)

**Files:**
- Create: `keys.py`
- Test: `tests/test_keys.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_keys.py
from keys import to_camelot, to_open_key, format_key


def test_to_camelot_minor_and_major():
    assert to_camelot("A Minor") == "8A"
    assert to_camelot("C Major") == "8B"
    assert to_camelot("E Minor") == "9A"


def test_to_camelot_accidentals_and_short_forms():
    assert to_camelot("F# Minor") == "11A"
    assert to_camelot("Db Major") == "3B"   # flat normalised to C#
    assert to_camelot("A min") == "8A"      # short mode token


def test_to_camelot_unknown_returns_none():
    assert to_camelot("Not A Key") is None
    assert to_camelot("") is None
    assert to_camelot(None) is None


def test_to_open_key():
    assert to_open_key("8A") == "1m"   # A minor
    assert to_open_key("8B") == "1d"   # C major
    assert to_open_key("9A") == "2m"
    assert to_open_key(None) is None


def test_format_key_derives_from_name():
    assert format_key({"name": "A Minor"}) == "A Minor (Camelot 8A, Open Key 1m)"


def test_format_key_prefers_native_camelot_fields():
    obj = {"name": "C Major", "camelot_number": 8, "camelot_letter": "B"}
    assert format_key(obj) == "C Major (Camelot 8B, Open Key 1d)"


def test_format_key_falls_back_to_plain_name():
    assert format_key({"name": "Weird"}) == "Weird"
    assert format_key(None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_keys.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'keys'`.

- [ ] **Step 3: Implement `keys.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_keys.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add keys.py tests/test_keys.py
git commit -m "feat: neutral Camelot/Open-Key notation module"
```

---

## Task 3: Token store & refresh (`auth.py`)

**Files:**
- Create: `auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auth.py
import json

import httpx
import pytest
import respx

from auth import TokenStore, refresh_tokens, build_authorize_url, pkce_pair


def test_token_store_round_trips_to_file(tmp_path):
    path = tmp_path / "token.json"
    store = TokenStore(client_id="cid", access_token="a", refresh_token="r", path=path)
    store.update(access_token="a2", refresh_token="r2")
    assert json.loads(path.read_text())["access_token"] == "a2"
    reloaded = TokenStore(client_id="cid", path=path)
    assert reloaded.access_token == "a2"
    assert reloaded.refresh_token == "r2"


def test_from_env_reads_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("CLIENT_ID", "cid")
    monkeypatch.setenv("ACCESS_TOKEN", "a")
    monkeypatch.setenv("REFRESH_TOKEN", "r")
    monkeypatch.setenv("BEATPORT_TOKEN_PATH", str(tmp_path / "t.json"))
    store = TokenStore.from_env()
    assert (store.client_id, store.access_token, store.refresh_token) == ("cid", "a", "r")


def test_pkce_pair_and_authorize_url():
    verifier, challenge = pkce_pair()
    assert 43 <= len(verifier) <= 128
    url = build_authorize_url(client_id="cid", redirect_uri="http://localhost:8765/callback",
                              challenge=challenge)
    assert url.startswith("https://api.beatport.com/v4/auth/o/authorize/?")
    assert "code_challenge_method=S256" in url
    assert "client_id=cid" in url


@respx.mock
async def test_refresh_tokens_posts_grant(tmp_path):
    route = respx.post("https://api.beatport.com/v4/auth/o/token/").mock(
        return_value=httpx.Response(200, json={"access_token": "new", "refresh_token": "r2"})
    )
    data = await refresh_tokens(client_id="cid", refresh_token="r")
    assert data["access_token"] == "new"
    sent = dict(httpx.QueryParams(route.calls.last.request.content.decode()))
    assert sent["grant_type"] == "refresh_token"
    assert sent["refresh_token"] == "r"
    assert sent["client_id"] == "cid"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auth'`.

- [ ] **Step 3: Implement `auth.py`**

```python
"""Beatport OAuth: token storage, refresh, and a one-time browser (PKCE) bootstrap.

Browser login is the primary, user-facing auth path. End users do not hand-copy
tokens. `TokenStore` holds credentials and persists refreshed tokens to a file so
refresh-token rotation survives restarts.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import httpx

API_BASE = "https://api.beatport.com/v4"
TOKEN_URL = f"{API_BASE}/auth/o/token/"
AUTHORIZE_URL = f"{API_BASE}/auth/o/authorize/"
DEFAULT_TOKEN_PATH = Path.home() / ".beatport-mcp" / "token.json"
REDIRECT_URI = "http://localhost:8765/callback"


def _token_path() -> Path:
    raw = os.environ.get("BEATPORT_TOKEN_PATH")
    return Path(raw).expanduser() if raw else DEFAULT_TOKEN_PATH


class TokenStore:
    """Holds OAuth credentials; persists refreshed tokens to a JSON file."""

    def __init__(self, client_id: str, access_token: str | None = None,
                 refresh_token: str | None = None, path: Path | None = None) -> None:
        self.client_id = client_id
        self.path = path or _token_path()
        self.access_token = access_token
        self.refresh_token = refresh_token
        if self.access_token is None and self.path.exists():
            saved = json.loads(self.path.read_text())
            self.access_token = saved.get("access_token")
            self.refresh_token = saved.get("refresh_token")

    @classmethod
    def from_env(cls) -> "TokenStore":
        client_id = os.environ.get("CLIENT_ID")
        if not client_id:
            raise RuntimeError("CLIENT_ID is not set. Run `uv run beatport-auth` first.")
        return cls(
            client_id=client_id,
            access_token=os.environ.get("ACCESS_TOKEN"),
            refresh_token=os.environ.get("REFRESH_TOKEN"),
        )

    def update(self, access_token: str, refresh_token: str | None) -> None:
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"access_token": self.access_token, "refresh_token": self.refresh_token}
        ))


async def refresh_tokens(client_id: str, refresh_token: str) -> dict:
    """Exchange a refresh token for a new access token."""
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        })
        resp.raise_for_status()
        return resp.json()


def pkce_pair() -> tuple[str, str]:
    """Return (verifier, challenge) for the PKCE S256 flow."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_authorize_url(client_id: str, redirect_uri: str, challenge: str) -> str:
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return f"{AUTHORIZE_URL}?{params}"


def main() -> None:
    """One-time browser PKCE bootstrap. Opens the browser, captures the code via a
    localhost callback, exchanges it, and persists the tokens.

    NOTE: client_id and a working redirect_uri are verify-live items (spec Sec 11 #1, #7).
    Until confirmed, paste CLIENT_ID/ACCESS_TOKEN/REFRESH_TOKEN from devtools into .env.
    """
    client_id = os.environ.get("CLIENT_ID")
    if not client_id:
        raise SystemExit("Set CLIENT_ID in the environment before running the bootstrap.")
    verifier, challenge = pkce_pair()
    code_box: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            query = urllib.parse.urlparse(self.path).query
            code_box.update(urllib.parse.parse_qs(query))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorized. You can close this tab.")

        def log_message(self, *_args) -> None:  # silence
            return

    server = http.server.HTTPServer(("localhost", 8765), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    webbrowser.open(build_authorize_url(client_id, REDIRECT_URI, challenge))
    print("Waiting for browser authorization...")
    while "code" not in code_box:
        pass
    code = code_box["code"][0] if isinstance(code_box["code"], list) else code_box["code"]
    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
    })
    resp.raise_for_status()
    tokens = resp.json()
    store = TokenStore(client_id=client_id)
    store.update(tokens["access_token"], tokens.get("refresh_token"))
    print(f"CLIENT_ID={client_id}")
    print(f"ACCESS_TOKEN={tokens['access_token']}")
    print(f"REFRESH_TOKEN={tokens.get('refresh_token')}")
    print(f"Tokens persisted to {store.path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: PASS (4 tests). The interactive `main()` is covered by manual smoke (Task 9), not unit tests.

- [ ] **Step 5: Commit**

```bash
git add auth.py tests/test_auth.py
git commit -m "feat: token store, async refresh, and PKCE bootstrap helpers"
```

---

## Task 4: HTTP client core (`client.py`)

**Files:**
- Create: `client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_client.py
import httpx
import pytest
import respx

from auth import TokenStore
from client import BeatportClient, BeatportError


def _store(tmp_path, access="tok"):
    return TokenStore(client_id="cid", access_token=access, refresh_token="r",
                      path=tmp_path / "token.json")


@respx.mock
async def test_request_resolves_v4_url_and_attaches_bearer(tmp_path):
    route = respx.get("https://api.beatport.com/v4/catalog/tracks/1/").mock(
        return_value=httpx.Response(200, json={"id": 1, "name": "X"})
    )
    client = BeatportClient(_store(tmp_path))
    data = await client.track(1)
    assert data["id"] == 1
    assert route.calls.last.request.headers["Authorization"] == "Bearer tok"
    assert route.calls.last.request.headers["Accept"] == "application/json"


@respx.mock
async def test_401_triggers_refresh_and_single_retry(tmp_path):
    track = respx.get("https://api.beatport.com/v4/catalog/tracks/1/")
    track.side_effect = [httpx.Response(401), httpx.Response(200, json={"id": 1})]
    respx.post("https://api.beatport.com/v4/auth/o/token/").mock(
        return_value=httpx.Response(200, json={"access_token": "new", "refresh_token": "r2"})
    )
    store = _store(tmp_path, access="old")
    client = BeatportClient(store)
    data = await client.track(1)
    assert data["id"] == 1
    assert store.access_token == "new"
    assert track.call_count == 2


@respx.mock
async def test_persistent_401_raises_friendly_error(tmp_path):
    respx.get("https://api.beatport.com/v4/catalog/tracks/1/").mock(
        return_value=httpx.Response(401)
    )
    respx.post("https://api.beatport.com/v4/auth/o/token/").mock(
        return_value=httpx.Response(200, json={"access_token": "new"})
    )
    client = BeatportClient(_store(tmp_path))
    with pytest.raises(BeatportError, match="Authentication failed"):
        await client.track(1)


@respx.mock
async def test_404_and_429_map_to_beatport_error(tmp_path):
    respx.get("https://api.beatport.com/v4/catalog/tracks/9/").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.beatport.com/v4/catalog/tracks/8/").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "30"})
    )
    client = BeatportClient(_store(tmp_path))
    with pytest.raises(BeatportError, match="Not found"):
        await client.track(9)
    with pytest.raises(BeatportError, match="30"):
        await client.track(8)


@respx.mock
async def test_search_clamps_per_page_and_drops_none(tmp_path):
    route = respx.get("https://api.beatport.com/v4/catalog/search/").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = BeatportClient(_store(tmp_path))
    await client.search("strobe", type="tracks", per_page=500)
    params = route.calls.last.request.url.params
    assert params["per_page"] == "100"      # clamped
    assert params["q"] == "strobe"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'client'`.

- [ ] **Step 3: Implement `client.py`**

```python
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


def _handle(resp: httpx.Response) -> dict:
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

    async def _request(self, path: str, params: dict | None = None) -> dict:
        clean = _clean_params(params)
        resp = await self._http.get(path, params=clean, headers=self._headers())
        if resp.status_code == 401:
            await self._refresh()
            resp = await self._http.get(path, params=clean, headers=self._headers())
        return _handle(resp)

    # --- endpoint methods (Plan A slice) ---
    async def search(self, query: str, type: str = "tracks",
                     page: int = 1, per_page: int = 25) -> dict:
        return await self._request("catalog/search/", {
            "q": query, "type": type, "page": page, "per_page": per_page,
        })

    async def track(self, track_id: int) -> dict:
        return await self._request(f"catalog/tracks/{track_id}/")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add client.py tests/test_client.py
git commit -m "feat: async Beatport client with refresh-on-401 and error mapping"
```

---

## Task 5: Live verification & fixture capture (gating)

This is the contract-verification step. It requires the user's working credentials in a local `.env` (gitignored). Output is **real captured fixtures** and any field-map corrections.

**Files:**
- Create: `scripts/verify.py`
- Create: `tests/fixtures/track.json`, `tests/fixtures/search_tracks.json` (captured here)

- [ ] **Step 1: Create the probe script**

```python
# scripts/verify.py
"""Manual live probe — NOT run in CI. Requires CLIENT_ID/ACCESS_TOKEN/REFRESH_TOKEN
in the environment (load a local .env). Dumps real JSON for fixture capture.

Usage: set -a; source .env; set +a; uv run python scripts/verify.py <track_id>
"""

import asyncio
import json
import sys

from auth import TokenStore
from client import BeatportClient


async def main() -> None:
    track_id = int(sys.argv[1]) if len(sys.argv) > 1 else 10000000
    client = BeatportClient(TokenStore.from_env())
    track = await client.track(track_id)
    search = await client.search("strobe", type="tracks", per_page=3)
    print("=== TRACK ===")
    print(json.dumps(track, indent=2)[:4000])
    print("=== SEARCH ===")
    print(json.dumps(search, indent=2)[:4000])


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the probe against the live API**

Run: `set -a; source .env; set +a; uv run python scripts/verify.py <a-real-track-id>`
Expected: real JSON for a track and a 3-result search.

- [ ] **Step 3: Record findings against the verification checklist (spec §11)**

Confirm and note each, in the commit message or a scratch note:
1. `client_id` value works for refresh.
2. Refresh-token rotation: does the refresh response include a new `refresh_token`?
3. Track `key` object: does it include `camelot_number`/`camelot_letter`? Exact `name` format (e.g. "A Min").
4. Search envelope key: `results` vs `data`; presence of `count`/`next`.
5. Field paths used by the formatters exist: `bpm`, `genre.name`, `length`, `release.name`, `release.label.name`, `release.publish_date`, preview field name (e.g. `sample_url`).
6. Trailing-slash behaviour on `catalog/search/` and `catalog/tracks/{id}/`.

- [ ] **Step 4: Capture sanitized fixtures**

Save the real track JSON to `tests/fixtures/track.json` and the search JSON to
`tests/fixtures/search_tracks.json`. Remove any token/PII fields. These become the
ground truth for Task 6/7/8 — and for Plan B.

- [ ] **Step 5: Reconcile field-map drift (only if findings differ)**

If item 3 shows a different `key.name` format, extend `keys._KEY_RE`/`_parse_key` and add a
test case. If the preview field is not `sample_url`, update the constant used in
`transform.format_track` (Task 6) and its fixture. If the search envelope key differs,
update `transform.format_search_results` (Task 7). Keep all tests green.

- [ ] **Step 6: Commit**

```bash
git add scripts/verify.py tests/fixtures/track.json tests/fixtures/search_tracks.json
git commit -m "test: live-verified fixtures and probe script; reconcile field map

Verification notes (spec §11): <fill the 6 findings here>"
```

---

## Task 6: Track formatter (`transform.format_track`)

**Files:**
- Create: `transform.py`
- Test: `tests/test_transform.py`

- [ ] **Step 1: Write the failing test**

Uses a hand-authored fixture matching the verified shape (adjust field names if Task 5 found drift):

```python
# tests/test_transform.py
import transform

TRACK = {
    "id": 12345678,
    "name": "Strobe",
    "mix_name": "Original Mix",
    "artists": [{"id": 1, "name": "deadmau5"}],
    "bpm": 128,
    "key": {"name": "A Minor"},
    "genre": {"id": 15, "name": "Progressive House"},
    "length": "10:33",
    "publish_date": "2009-09-22",  # top-level on the track (verified Task 5)
    "release": {
        "id": 999, "name": "For Lack of a Better Name",
        "label": {"id": 5, "name": "mau5trap"},
    },
    "sample_url": "https://geo-samples.beatport.com/strobe.mp3",
}


def test_format_track_full_block():
    out = transform.format_track(TRACK)
    assert out.splitlines()[0] == 'Track #12345678 — "Strobe" by deadmau5'
    assert "BPM: 128" in out
    assert "Key: A Minor (Camelot 8A, Open Key 1m)" in out
    assert "Genre: Progressive House" in out
    assert "Label: mau5trap" in out
    assert "Release: For Lack of a Better Name (2009-09-22)" in out
    assert "Preview: https://geo-samples.beatport.com/strobe.mp3" in out


def test_format_track_tolerates_missing_fields():
    out = transform.format_track({"id": 7, "name": "Bare", "artists": []})
    assert out.startswith('Track #7 — "Bare" by Unknown artist')


def test_format_track_real_fixture():
    # Grounds the formatter against the real captured Beatport track (Task 5).
    import json
    from pathlib import Path

    track = json.loads(Path("tests/fixtures/track.json").read_text())
    out = transform.format_track(track)
    assert out.startswith("Track #")
    assert "Camelot 1A" in out          # native camelot_number/letter passthrough
    assert "BPM:" in out
    assert "2024-09-13" in out          # top-level publish_date
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_transform.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'transform'`.

- [ ] **Step 3: Implement `transform.py` (track parts)**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_transform.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add transform.py tests/test_transform.py
git commit -m "feat: full single-track formatter"
```

---

## Task 7: List/search formatters (`transform.format_track_summary`, `format_search_results`)

**Files:**
- Modify: `transform.py`
- Test: `tests/test_transform.py`

- [ ] **Step 1: Add the failing tests**

```python
# append to tests/test_transform.py

def test_format_track_summary_compact_line():
    line = transform.format_track_summary(TRACK)
    assert line == "#12345678 — Strobe · deadmau5 · 128 BPM · A Minor (Camelot 8A, Open Key 1m)"


def test_format_search_results_tracks():
    # Beatport keys the result list by the search `type` (verified Task 5), not "results".
    data = {"tracks": [TRACK, {"id": 2, "name": "B", "artists": [{"name": "Y"}]}]}
    out = transform.format_search_results(data, "tracks")
    assert out.splitlines()[0].startswith("#12345678 — Strobe")
    assert out.splitlines()[1].startswith("#2 — B · Y")


def test_format_search_results_non_track_type():
    data = {"artists": [{"id": 3, "name": "Adam Beyer"}]}
    assert transform.format_search_results(data, "artists") == "#3 — Adam Beyer"


def test_format_search_results_empty():
    assert transform.format_search_results({"tracks": []}, "tracks") == "No results."


def test_format_search_results_real_fixture():
    # Grounds against the real captured search payload (Task 5).
    import json
    from pathlib import Path

    data = json.loads(Path("tests/fixtures/search_tracks.json").read_text())
    out = transform.format_search_results(data, "tracks")
    assert out                                  # non-empty
    assert all(line.startswith("#") for line in out.splitlines())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_transform.py -v`
Expected: FAIL with `AttributeError: module 'transform' has no attribute 'format_track_summary'`.

- [ ] **Step 3: Implement the list formatters (append to `transform.py`)**

```python
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
        return "\n".join(format_track_summary(t) for t in items)
    return "\n".join(f"#{item.get('id')} — {item.get('name', '?')}" for item in items)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_transform.py -v`
Expected: PASS (8 tests total in file).

- [ ] **Step 5: Commit**

```bash
git add transform.py tests/test_transform.py
git commit -m "feat: compact track-summary and search-result formatters"
```

---

## Task 8: Server tools & entry point (`server.py`, `main.py`)

**Files:**
- Create: `server.py`
- Create: `main.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing tests**

Tools are tested by monkeypatching the lazy client so no network is hit:

```python
# tests/test_server.py
import pytest

import server


class _FakeClient:
    async def track(self, track_id):
        return {"id": track_id, "name": "Strobe", "artists": [{"name": "deadmau5"}]}

    async def search(self, query, type="tracks", page=1, per_page=25):
        return {"tracks": [{"id": 1, "name": query, "artists": [{"name": "Z"}]}]}


@pytest.fixture(autouse=True)
def _fake(monkeypatch):
    monkeypatch.setattr(server, "_get_client", lambda: _FakeClient())


async def test_get_track_tool_formats_output():
    out = await server.get_track(12345678)
    assert out.startswith('Track #12345678 — "Strobe" by deadmau5')


async def test_search_tool_formats_output():
    out = await server.search("strobe")
    assert out.startswith("#1 — strobe · Z")


async def test_tool_errors_return_strings(monkeypatch):
    class _Boom:
        async def track(self, track_id):
            from client import BeatportError
            raise BeatportError("Not found.")
    monkeypatch.setattr(server, "_get_client", lambda: _Boom())
    out = await server.get_track(1)
    assert out == "Error: Not found."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server'`.

- [ ] **Step 3: Implement `server.py`**

```python
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
```

- [ ] **Step 4: Implement `main.py`**

```python
from server import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_server.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the full suite + linters**

Run: `uv run pytest -q && uv run ruff check . && uv run pyright`
Expected: all tests pass; ruff clean; pyright no errors.

- [ ] **Step 7: Commit**

```bash
git add server.py main.py tests/test_server.py
git commit -m "feat: FastMCP server with search and get_track tools"
```

---

## Task 9: End-to-end smoke in Claude + README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Verify the server launches**

Run: `set -a; source .env; set +a; uv run beatport-mcp`
Expected: process starts and waits on stdio (no crash). Ctrl-C to stop.

- [ ] **Step 2: Rewrite `README.md` setup section**

Fix the invalid JSON (`=`→`:`, quoted values) and the env vars to match the code. Replace the
config block with:

```json
{
  "mcpServers": {
    "beatport": {
      "command": "uv",
      "args": ["--directory", "/path/to/beatport-mcp", "run", "beatport-mcp"],
      "env": {
        "CLIENT_ID": "YOUR_CLIENT_ID",
        "ACCESS_TOKEN": "YOUR_ACCESS_TOKEN",
        "REFRESH_TOKEN": "YOUR_REFRESH_TOKEN"
      }
    }
  }
}
```

Document: (a) the one-time `uv run beatport-auth` browser login (with the verify-live caveat
that, until the redirect/client_id are confirmed, tokens can be pasted from devtools), and
(b) the two available tools.

- [ ] **Step 3: Connect to Claude Desktop and exercise both tools**

In Claude Desktop with the config above, confirm:
- "Search Beatport for strobe" → returns a track list with IDs.
- "Get details for track <id>" → returns the full formatted block with BPM and Camelot key.

Capture a screenshot for the PR.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: correct setup config, document browser-login bootstrap and tools"
```

---

## Task 10: Push & open the PR

- [ ] **Step 1: Fork and set remotes**

```bash
gh repo fork larsenweigle/beatport-mcp --remote --remote-name fork
git remote rename origin upstream
git remote rename fork origin
```

- [ ] **Step 2: Rebase on latest upstream (Larsen commits daily)**

```bash
git fetch upstream && git rebase upstream/main
```
Resolve any conflicts, keep tests green: `uv run pytest -q`.

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin feat/catalog-tools
gh pr create --repo larsenweigle/beatport-mcp --base main \
  --title "feat: read-only catalog tools (search, get_track) + auth/client foundation" \
  --body "<summary, setup changes, screenshot, note that Plan B adds the remaining catalog tools>"
```

- [ ] **Step 4: Confirm CI/green**

Expected: PR opens against `larsenweigle/beatport-mcp`; the spec and this plan are included
under `docs/superpowers/` for reviewer context (or dropped from the PR if Larsen prefers — decide
at review time).

---

## Self-Review

**Spec coverage:**
- §4 architecture/layout/deps/tooling → Task 1. ✓
- §5 components: `TokenStore`/refresh → Task 3; `BeatportClient`/`_handle`/`_clean_params` → Task 4; `keys` → Task 2; `transform` → Tasks 6–7; `server`/`main` → Task 8. ✓
- §6 tool surface: `search` + `get_track` → Task 8 (the Plan A slice; remaining 7 tools = Plan B, called out in header). ✓ (intentional split)
- §7 auth lifecycle (browser bootstrap + env seed + refresh + rotation persistence) → Tasks 3, 9. ✓
- §8 data flow / §9 error handling → Task 4 (`_request`, `_handle`). ✓
- §10 testing (pure unit + respx + fixtures + manual smoke out of CI) → Tasks 2–8 + `scripts/verify.py` (Task 5). ✓
- §11 live-verification checklist → Task 5. ✓
- §12 contribution mechanics → Task 10. ✓
- Faithful cleanups (weather boilerplate, `.gitignore`, README JSON/env, drop `requests`) → Tasks 1, 9. ✓

**Placeholder scan:** the only deferred content is Task 5's verification *findings* and Task 9/10's PR body/screenshot — these are genuine runtime outputs, not code placeholders. All code steps contain complete code.

**Type consistency:** `TokenStore(client_id, access_token, refresh_token, path)`, `.update(access_token, refresh_token)`, `.from_env()`, `refresh_tokens(client_id, refresh_token)`, `BeatportClient(store, http=None)`, `_request(path, params)`, `format_key(dict|None)`, `format_track(dict)`, `format_track_summary(dict)`, `format_search_results(data, type)`, `server._get_client()` — all names match across Tasks 3, 4, 6, 7, 8. ✓

**Task 5 reconciliation (applied):** the live probe corrected three assumptions, now baked into Tasks 6–8:
- Search result list is keyed by the `type` (e.g. `{"tracks": [...]}`), NOT `results`/`data`. Other top-level keys: `count`, `page` (string `"1/1035"`), `per_page`, `next`, `previous`, `order`.
- `publish_date` is **top-level on the track**, not under `release`.
- `key` carries native `camelot_number`/`camelot_letter` (e.g. "Ab Minor" → 1A), so `format_key` uses Beatport's own Camelot; preview field is `sample_url`; trailing slashes work; `key.name` is full-word ("Ab Minor"). The `keys.py` parser handles this format and agrees with the native value as a fallback.
