# Beatport MCP — Plan B: Remaining Catalog Tools

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add the remaining 7 read-only catalog tools on top of the verified Plan A foundation: `list_tracks`, `list_genres`, `get_artist`, `get_release`, `get_label`, `get_genre`, `get_chart`.

**Architecture:** Same layering as Plan A — new client methods (I/O), new pure formatters (`transform.py`), a key-name→id helper (`keys.py`), and `@mcp.tool()` wrappers (`server.py`). All contracts and fixtures were captured live (Task 18 + key sweep) and committed under `tests/fixtures/`.

**Tech Stack:** Python 3.12, mcp[cli], httpx, uv, ruff, pyright, pytest + respx.

**Branch:** continue on `feat/catalog-tools`.

---

## Verified contracts (live, 2026-06-13) — the source of truth

**Envelopes.** Plain list endpoints use `{count, next, previous, page, per_page, results}` (the item list is `results`). The search endpoint (Plan A) is different — it keys items by `type`. `page` is a string like `"1/3334"`.

**`count` caveat.** `count` is hard-capped at `10000` for `catalog/tracks/` and `genres/{id}/tracks/` (large buckets); it is the **real** total for artist/release/chart tracks and label releases. Footer must render `10000+` for the sentinel.

| Tool | Endpoint(s) | Notes |
|---|---|---|
| `list_tracks` | `GET catalog/tracks/` | filters: `genre_id`, `artist_id`, `label_id`, `bpm` (EXACT only), `key_id`, `name` (substring), `ordering` (`publish_date`/`-publish_date` only). BPM range & ordering-by-bpm NOT supported. |
| `list_genres` | `GET catalog/genres/` | 46 genres; item keys incl. `id`, `name`, `slug`, `sub_genres`. |
| `get_artist` | `GET catalog/artists/{id}/` + `…/artists/{id}/tracks/` | detail keys: `id`, `name`, `bio`, `website`, `image`, `slug`. No `top-N-tracks` endpoint — use `/tracks/`. |
| `get_release` | `GET catalog/releases/{id}/` + `…/releases/{id}/tracks/` | detail `tracks` field is a list of URL strings; use `/tracks/` for full objects. detail keys incl. `id`, `name`, `artists`, `label`, `catalog_number`, `publish_date`, `track_count`. |
| `get_label` | `GET catalog/labels/{id}/` + `…/labels/{id}/releases/` | NO label tracks sub-endpoint; labels expose `/releases/`. detail keys incl. `id`, `name`, `bio`. |
| `get_genre` | `GET catalog/genres/{id}/` + `…/genres/{id}/tracks/` | detail keys: `id`, `name`, `slug`, `sub_genres`. |
| `get_chart` | `GET catalog/charts/{id}/` + `…/charts/{id}/tracks/` | detail keys incl. `id`, `name`, `artist`, `track_count`, `publish_date`, `description`. |

**Key map.** `catalog/keys/` is `403`. The full key_id→name map was swept via `?key_id=N` and saved to `tests/fixtures/keys_map.json`. Canonical ids 1–24 cover all 24 keys (1–12 minor, 13–24 major); ids 25–34 are enharmonic alternates. `key` filtering takes a `key_id`, so a name→id helper is needed.

## File structure

| File | Change |
|---|---|
| `keys.py` | add `key_name_to_id(name)` (reuses `_parse_key`) |
| `client.py` | add endpoint methods (genres, genre, genre_tracks, artist, artist_tracks, release, release_tracks, label, label_releases, charts list/get, chart_tracks, list_tracks) |
| `transform.py` | add detail formatters (`format_artist/release/label/genre/chart`) + list formatters (`format_track_list`, `format_genre_list`, `format_release_list`, `_pagination_footer`) |
| `server.py` | add 7 `@mcp.tool()` wrappers |
| `tests/` | new tests per module, grounded on committed fixtures |
| `README.md` | extend the tools table |

---

## Task B1: Key-name → key_id helper (`keys.py`)

**Files:** Modify `keys.py`; modify `tests/test_keys.py`.

- [ ] **Step 1: Append failing tests to `tests/test_keys.py`**

```python


def test_key_name_to_id_canonical():
    from keys import key_name_to_id
    assert key_name_to_id("A Minor") == 8
    assert key_name_to_id("C Major") == 20
    assert key_name_to_id("Ab Minor") == 1
    assert key_name_to_id("Db Major") == 15
    assert key_name_to_id("F# Minor") == 11


def test_key_name_to_id_short_and_enharmonic_forms():
    from keys import key_name_to_id
    assert key_name_to_id("A min") == 8          # short mode token
    assert key_name_to_id("G# Minor") == 1       # enharmonic of Ab Minor -> canonical id 1
    assert key_name_to_id("A# Minor") == 3       # enharmonic of Bb Minor -> canonical id 3


def test_key_name_to_id_unknown():
    from keys import key_name_to_id
    assert key_name_to_id("not a key") is None
    assert key_name_to_id("") is None
    assert key_name_to_id(None) is None


def test_key_name_to_id_matches_live_map():
    # Every canonical id (1-24) in the live sweep must round-trip by name.
    import json
    from pathlib import Path
    from keys import key_name_to_id
    m = json.loads(Path("tests/fixtures/keys_map.json").read_text())
    for sid, entry in m.items():
        if 1 <= int(sid) <= 24:
            assert key_name_to_id(entry["name"]) == int(sid), entry["name"]
```

- [ ] **Step 2: Run — expect FAIL** (`ImportError: cannot import name 'key_name_to_id'`).
Run: `uv run pytest tests/test_keys.py -v`

- [ ] **Step 3: Append to `keys.py`**

```python
# Canonical Beatport key_ids 1-24 (verified live). Keyed by (_parse_key root, mode);
# flats are normalised to sharps by _parse_key, so each (root, mode) maps to one id.
_NAME_TO_ID: dict[tuple[str, str], int] = {
    ("G#", "minor"): 1, ("D#", "minor"): 2, ("A#", "minor"): 3, ("F", "minor"): 4,
    ("C", "minor"): 5, ("G", "minor"): 6, ("D", "minor"): 7, ("A", "minor"): 8,
    ("E", "minor"): 9, ("B", "minor"): 10, ("F#", "minor"): 11, ("C#", "minor"): 12,
    ("B", "major"): 13, ("F#", "major"): 14, ("C#", "major"): 15, ("G#", "major"): 16,
    ("D#", "major"): 17, ("A#", "major"): 18, ("F", "major"): 19, ("C", "major"): 20,
    ("G", "major"): 21, ("D", "major"): 22, ("A", "major"): 23, ("E", "major"): 24,
}


def key_name_to_id(name: str | None) -> int | None:
    """Resolve a musical key name (e.g. 'A minor', 'Ab Minor', 'A# min') to Beatport's
    canonical key_id (1-24). Enharmonic spellings resolve to the same canonical id."""
    parsed = _parse_key(name)
    return _NAME_TO_ID.get(parsed) if parsed else None
```

- [ ] **Step 4: Run — expect PASS.** `uv run pytest tests/test_keys.py -v`
- [ ] **Step 5: Lint.** `uv run ruff check keys.py tests/test_keys.py && uv run pyright keys.py`
- [ ] **Step 6: Commit.**
```bash
git add keys.py tests/test_keys.py
git commit -m "feat: resolve musical key names to Beatport key_id"
```

---

## Task B2: Client endpoint methods (`client.py`)

**Files:** Modify `client.py`; modify `tests/test_client.py`.

- [ ] **Step 1: Append failing tests to `tests/test_client.py`**

```python


@respx.mock
async def test_list_tracks_builds_filters(tmp_path):
    route = respx.get("https://api.beatport.com/v4/catalog/tracks/").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = BeatportClient(_store(tmp_path))
    await client.list_tracks(genre_id=5, bpm=128, key_id=8, ordering="-publish_date", per_page=10)
    p = route.calls.last.request.url.params
    assert p["genre_id"] == "5" and p["bpm"] == "128" and p["key_id"] == "8"
    assert p["ordering"] == "-publish_date" and p["per_page"] == "10"


@respx.mock
async def test_entity_endpoints_resolve_paths(tmp_path):
    for path in [
        "catalog/genres/", "catalog/genres/5/", "catalog/genres/5/tracks/",
        "catalog/artists/9/", "catalog/artists/9/tracks/",
        "catalog/releases/7/", "catalog/releases/7/tracks/",
        "catalog/labels/3/", "catalog/labels/3/releases/",
        "catalog/charts/", "catalog/charts/2/", "catalog/charts/2/tracks/",
    ]:
        respx.get(f"https://api.beatport.com/v4/{path}").mock(
            return_value=httpx.Response(200, json={"results": [], "id": 1})
        )
    client = BeatportClient(_store(tmp_path))
    assert await client.genres() == {"results": [], "id": 1}
    assert await client.genre(5) is not None
    assert await client.genre_tracks(5) is not None
    assert await client.artist(9) is not None
    assert await client.artist_tracks(9) is not None
    assert await client.release(7) is not None
    assert await client.release_tracks(7) is not None
    assert await client.label(3) is not None
    assert await client.label_releases(3) is not None
    assert await client.charts() is not None
    assert await client.chart(2) is not None
    assert await client.chart_tracks(2) is not None
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError: 'BeatportClient' object has no attribute 'list_tracks'`).
Run: `uv run pytest tests/test_client.py -v`

- [ ] **Step 3: Append these methods inside the `BeatportClient` class in `client.py`** (after `track`)

```python
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
```

- [ ] **Step 4: Run — expect PASS.** `uv run pytest tests/test_client.py -v`
- [ ] **Step 5: Lint.** `uv run ruff check client.py tests/test_client.py && uv run pyright client.py`
- [ ] **Step 6: Commit.**
```bash
git add client.py tests/test_client.py
git commit -m "feat: client methods for catalog list/detail endpoints"
```

---

## Task B3: Formatters (`transform.py`)

**Files:** Modify `transform.py`; modify `tests/test_transform.py`.

- [ ] **Step 1: Append failing tests to `tests/test_transform.py`**

```python


def _fixture(name):
    import json
    from pathlib import Path
    return json.loads(Path(f"tests/fixtures/{name}").read_text())


def test_format_track_list_with_capped_count():
    out = transform.format_track_list(_fixture("list_tracks.json"))
    lines = out.splitlines()
    assert all(line.startswith("#") for line in lines[:-1])
    assert lines[-1].startswith("Page ")
    assert "10000+ results" in lines[-1]          # count==10000 sentinel


def test_format_track_list_real_count():
    out = transform.format_track_list(_fixture("chart_tracks.json"))
    assert out.splitlines()[-1] == "Page 1/8 · 39 results"   # real count


def test_format_track_list_empty():
    assert transform.format_track_list({"results": []}) == "No tracks."


def test_format_genre_list():
    out = transform.format_genre_list(_fixture("genres_list.json"))
    assert out.splitlines()[0].startswith("#")
    assert " — " in out.splitlines()[0]


def test_format_artist_header():
    out = transform.format_artist(_fixture("artist.json"))
    assert out.startswith("Artist #")


def test_format_release_header_and_list():
    out = transform.format_release(_fixture("release.json"))
    assert out.startswith("Release #")
    rl = transform.format_release_list(_fixture("label_releases.json"))
    assert rl.splitlines()[0].startswith("#")
    assert rl.splitlines()[-1].startswith("Page ")


def test_format_label_and_genre_and_chart_headers():
    assert transform.format_label(_fixture("label.json")).startswith("Label #")
    assert transform.format_genre(_fixture("genre.json")).startswith("Genre #")
    assert transform.format_chart(_fixture("chart.json")).startswith("Chart #")
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError: ... 'format_track_list'`).
Run: `uv run pytest tests/test_transform.py -v`

- [ ] **Step 3: Append to `transform.py`**

```python
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
    lines = [f"Release #{release.get('id')} — \"{release.get('name', 'Untitled')}\" by {_artist_names(release)}"]
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
```

- [ ] **Step 4: Run — expect PASS.** `uv run pytest tests/test_transform.py -v`
- [ ] **Step 5: Lint.** `uv run ruff check transform.py tests/test_transform.py && uv run pyright transform.py`
- [ ] **Step 6: Commit.**
```bash
git add transform.py tests/test_transform.py
git commit -m "feat: detail and list formatters for catalog entities"
```

---

## Task B4: Server tools (`server.py`)

**Files:** Modify `server.py`; modify `tests/test_server.py`.

- [ ] **Step 1: Append failing tests to `tests/test_server.py`**

```python


class _CatalogClient:
    async def list_tracks(self, **kw):
        self.last = kw
        return {"results": [{"id": 1, "name": "T", "artists": [{"name": "A"}]}], "page": "1/1", "count": 1}

    async def genres(self, per_page=100):
        return {"results": [{"id": 14, "name": "Melodic House & Techno"}]}

    async def artist(self, artist_id):
        return {"id": artist_id, "name": "deadmau5"}

    async def artist_tracks(self, artist_id, per_page=25):
        return {"results": [{"id": 2, "name": "Strobe", "artists": [{"name": "deadmau5"}]}], "count": 1}

    async def release(self, release_id):
        return {"id": release_id, "name": "R", "artists": [{"name": "A"}]}

    async def release_tracks(self, release_id, per_page=25):
        return {"results": [{"id": 3, "name": "Trk", "artists": [{"name": "A"}]}], "count": 1}

    async def label(self, label_id):
        return {"id": label_id, "name": "mau5trap"}

    async def label_releases(self, label_id, per_page=25):
        return {"results": [{"id": 4, "name": "Rel", "artists": [{"name": "A"}], "track_count": 2}], "count": 1}

    async def genre(self, genre_id):
        return {"id": genre_id, "name": "Techno"}

    async def genre_tracks(self, genre_id, per_page=25):
        return {"results": [{"id": 5, "name": "GT", "artists": [{"name": "A"}]}], "count": 10000}

    async def chart(self, chart_id):
        return {"id": chart_id, "name": "Chart"}

    async def chart_tracks(self, chart_id, per_page=25):
        return {"results": [{"id": 6, "name": "CT", "artists": [{"name": "A"}]}], "count": 1}


@pytest.fixture
def _catalog(monkeypatch):
    c = _CatalogClient()
    monkeypatch.setattr(server, "_get_client", lambda: c)
    return c


async def test_list_tracks_resolves_key_name(_catalog):
    out = await server.list_tracks(key="A minor", bpm=128)
    assert _catalog.last["key_id"] == 8        # "A minor" -> 8
    assert _catalog.last["bpm"] == 128
    assert out.startswith("#1")


async def test_list_tracks_unknown_key_errors(_catalog):
    out = await server.list_tracks(key="not a key")
    assert out.startswith("Error:") and "key" in out.lower()


async def test_list_tracks_newest_first_ordering(_catalog):
    await server.list_tracks(genre_id=1, newest_first=True)
    assert _catalog.last["ordering"] == "-publish_date"
    await server.list_tracks(genre_id=1, newest_first=False)
    assert _catalog.last["ordering"] == "publish_date"


async def test_list_genres(_catalog):
    out = await server.list_genres()
    assert out.startswith("#14 — Melodic House & Techno")


async def test_get_artist_combines_detail_and_tracks(_catalog):
    out = await server.get_artist(9)
    assert out.startswith("Artist #9 — deadmau5")
    assert "Strobe" in out


async def test_get_release_and_label_and_genre_and_chart(_catalog):
    assert (await server.get_release(7)).startswith("Release #7")
    assert "mau5trap" in (await server.get_label(3))
    assert (await server.get_genre(5)).startswith("Genre #5")
    assert (await server.get_chart(2)).startswith("Chart #2")
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError: module 'server' has no attribute 'list_tracks'`).
Run: `uv run pytest tests/test_server.py -v`

- [ ] **Step 3: Append to `server.py`** (after `search`). Add `from keys import key_name_to_id` to the imports.

```python
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
            return f"Error: unrecognised musical key '{key}'. Use a form like 'A minor' or 'F# major'."
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
    """List all Beatport genres with their IDs (use an ID to filter list_tracks or call get_genre)."""
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
    return transform.format_label(detail) + "\n\nReleases:\n" + transform.format_release_list(releases)


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
```

- [ ] **Step 4: Run — expect PASS.** `uv run pytest tests/test_server.py -v`
- [ ] **Step 5: Lint.** `uv run ruff check server.py tests/test_server.py && uv run pyright server.py`
- [ ] **Step 6: Full suite.** `uv run pytest -q` (all green).
- [ ] **Step 7: Commit.**
```bash
git add server.py tests/test_server.py
git commit -m "feat: list_tracks, list_genres, and get_artist/release/label/genre/chart tools"
```

---

## Task B5: README + final verification

**Files:** Modify `README.md`.

- [ ] **Step 1: Extend the tools table in `README.md`** to include all 9 tools — add rows for
`list_tracks` (note exact-bpm + key-by-name), `list_genres`, `get_artist`, `get_release`,
`get_label`, `get_genre`, `get_chart`. Keep the existing `search`/`get_track` rows.

- [ ] **Step 2: Full verification.**
Run: `uv run pytest -q` (expect all green), `uv run ruff check .` (clean), `uv run pyright` (clean).

- [ ] **Step 3: MCP protocol smoke** — confirm all 9 tools advertise over stdio:
```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"s","version":"0"}}}' '{"jsonrpc":"2.0","method":"notifications/initialized"}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | uv run beatport-mcp 2>/dev/null | python3 -c "import sys,json;[print(sorted(t['name'] for t in json.loads(l).get('result',{}).get('tools',[]))) for l in sys.stdin if l.strip() and 'tools' in l]"
```
Expect: `['get_artist', 'get_chart', 'get_genre', 'get_label', 'get_release', 'get_track', 'list_genres', 'list_tracks', 'search']`.

- [ ] **Step 4: Commit.**
```bash
git add README.md
git commit -m "docs: document the full catalog tool surface"
```

---

## Self-Review

**Spec coverage:** all 7 Plan B tools implemented (B4), each backed by client methods (B2) and formatters (B3); key-name filtering via B1. ✓

**Contract fidelity:** every endpoint path, the `results` envelope, the `10000`-count sentinel, the exact-bpm/key_id/ordering filters, and the no-`top-N` reality are taken from the live probe and asserted against committed fixtures. ✓

**Placeholder scan:** none — all steps contain real code; tests assert against real captured fixtures. ✓

**Type consistency:** client methods return `dict[str, Any]`; `key_name_to_id -> int | None`; formatters take `dict` → `str`; tool names match across B2/B3/B4. `_artist_names` (Plan A) is reused by release/track formatters and works on the `artists` list present in both. ✓

**Known limitation (documented in the `list_tracks` docstring):** BPM is exact-only (no server-side range); enharmonic key spellings resolve to one canonical id, so a single key filter may miss tracks tagged under the alternate spelling.
