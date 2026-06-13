# Beatport MCP — Read-Only Catalog Server Design

- **Date:** 2026-06-13
- **Status:** Approved (design) — pending spec review
- **Repo:** `larsenweigle/beatport-mcp` (contributing upstream via fork → PR)
- **Author:** Khaled Yassin (contribution to Larsen Weigle's project)

## 1. Background

`beatport-mcp` is an MCP server for the Beatport Developer API. The current repo is an
early scaffold: `beatport.py` instantiates `FastMCP("beatport")` but defines **zero tools**
and still carries leftover National Weather Service boilerplate from the official MCP Python
quickstart (`NWS_API_BASE`). `auth.py` is a standalone token script using the deprecated
password grant and is not wired into the server. The documented launch command
(`uv run beatport-mcp`) fails because there is no `[project.scripts]` entry.

This design takes the project from scaffold to a working, **neutral, faithful, read-only
catalog** MCP server that Claude can use, while staying lightweight and idiomatic.

The Beatport public docs (`https://api.beatport.com/v4/docs/`) are a JS-rendered SPA and are
not machine-readable without a browser. Endpoint contracts here are reconstructed from
community sources (kemo gist, beets-beatport4, music-assistant) and will be **verified live**
against a real token (see §11).

## 2. Goals / Non-Goals

### Goals
- Full **read-only catalog** coverage: search, tracks, releases, artists, labels, genres, charts.
- **Neutral and faithful** to the API — serves any consumer (DJ, label A&R, journalist, analyst).
- LLM-ergonomic responses: trimmed, readable text blocks, each item led by its ID.
- Camelot / Open-Key included as **neutral additive key metadata** (a factual alternate
  encoding of Beatport's own key), with **no** harmonic/compatibility/workflow logic.
- Lightweight, idiomatic modern Python: uv, ruff, pyright, pytest; minimal dependencies.
- Mergeable upstream as a focused PR.

### Non-Goals (this contribution)
- Personal-library / user-account tools (`/my/...`) and full user OAuth consent UX.
- Harmonic-mixing / set-building / recommendation tools (opinionated workflow logic).
- Write operations of any kind.
- Auto-generated-from-OpenAPI or generic passthrough tooling.

## 3. Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | Full read-only catalog; no personal library |
| Architecture | Approach A — layered: `client` / `transform` / `server`, separate `auth` |
| Auth | Browser PKCE bootstrap CLI (primary user-facing auth) → env/file-seeded tokens + auto-refresh on 401 |
| Tool design | Thin wrappers, LLM-trimmed responses, neutral key-notation enrichment |
| DJ layer | Camelot as neutral additive metadata; no workflow logic in core |
| Verification | User has live access — verify contracts and capture real fixtures |
| Contribution | Fork → feature branch → PR (no upstream heads-up) |
| Token origin (current) | Grabbed from browser devtools; `client_id` to be identified during verify |

## 4. Architecture

Flat modules at repo root (faithful to Larsen's existing structure and the quickstart; no
`src/` layout):

```
beatport-mcp/
├── server.py        # FastMCP instance + @mcp.tool() defs + main() runner
├── client.py        # BeatportClient: async httpx I/O, bearer auth, refresh-on-401
├── transform.py     # pure functions: trim + format raw JSON → readable text (no I/O)
├── keys.py          # neutral key-notation translator (musical key → Camelot/Open-Key)
├── auth.py          # one-time PKCE bootstrap CLI + token store (env seed / file persist)
├── main.py          # thin console-script entry → server.main()
├── pyproject.toml   # deps, [project.scripts], tool configs
├── .env.example     # documents required env vars (no secrets)
└── tests/
    ├── test_transform.py     # pure unit tests, no network
    ├── test_client.py        # respx-mocked httpx
    └── fixtures/             # real captured API JSON (sanitized)
```

**Separation of concerns:** `client` = how we talk to Beatport; `transform`/`keys` = how we
make a response useful; `server` = what tools exist; `auth` = how we get/keep a token. The
pure modules (`transform`, `keys`) test with zero network.

### Dependencies
- **Runtime:** `mcp[cli]`, `httpx`. **Remove `requests`** (auth moves to httpx for coherence).
- **Dev (`[dependency-groups]`):** `ruff`, `pyright`, `pytest`, `pytest-asyncio`, `respx`.

### Tooling (configured in `pyproject.toml`)
- **uv** for env/deps/run; add `[project.scripts]` entries `beatport-mcp = "main:main"` (fixes
  broken launch) and `beatport-auth = "auth:main"` (the browser-login bootstrap).
- **ruff** for lint + format (single tool).
- **pyright** strict-ish; full type hints (FastMCP derives tool schemas from hints + docstrings).
- **pytest** + `pytest-asyncio`.

### Faithful cleanups folded in
- Delete `NWS_API_BASE` weather boilerplate.
- Fix `.gitignore` (currently ignores `soundcloud_token.json`, not the Beatport token file).
- Reconcile README env vars (`CLIENT_ID`/`ACCESS_TOKEN`/`REFRESH_TOKEN`) and fix its invalid JSON.

## 5. Components

### `client.py` — `BeatportClient`
- Holds an `httpx.AsyncClient`, base URL `https://api.beatport.com/v4/`, and a `TokenStore`.
- `async _request(path, params=None) -> dict` — attaches `Authorization: Bearer`, `Accept: application/json`;
  on `401`, calls `TokenStore.refresh()` and retries **once**; maps errors via `_handle()`.
- Thin typed methods per endpoint, e.g. `search()`, `tracks()`, `track(id)`, `artist(id)`,
  `artist_top_tracks(id)`, `release(id)`, `label(id)`, `label_top_tracks(id)`, `genres()`,
  `genre(id)`, `genre_top_tracks(id)`, `genre_top_releases(id)`, `chart(id)`.
- A pagination helper normalizes `page`/`per_page` (clamp `per_page` ≤ 100).

### `TokenStore` (in `auth.py`, used by client)
- Seeds from env (`CLIENT_ID`, `ACCESS_TOKEN`, `REFRESH_TOKEN`).
- `refresh()` → `POST /auth/o/token/` with `grant_type=refresh_token`, `refresh_token`, `client_id`.
- **Rotation safety:** persists refreshed tokens to a small JSON file (path via
  `BEATPORT_TOKEN_PATH`, default `~/.beatport-mcp/token.json`); env = initial seed, file = live
  state. Degrades gracefully if Beatport does not rotate refresh tokens (verify in §11).

### `transform.py` — pure formatters
- One formatter per entity: `format_track`, `format_artist`, `format_release`, `format_label`,
  `format_genre`, `format_chart`, plus compact `*_summary` variants for list items.
- Output is **readable text** (quickstart idiom), each item **led by its ID** so Claude can chain calls.
- No I/O; takes raw dict, returns `str`. Tolerant of missing fields.

### `keys.py` — neutral key-notation
- `to_camelot(key) -> (camelot, open_key) | None`: static 24-key lookup (12 major + 12 minor).
- If Beatport already returns Camelot data in its `key` object (verify §11), this becomes a thin
  pass-through and the static table is a fallback only.

### `server.py`
- `mcp = FastMCP("beatport")`; one `@mcp.tool()` per §6 tool; each is ~5 lines: call client →
  pass through transform → return string. Holds a module-level `BeatportClient` built at startup.
- `def main(): mcp.run(transport="stdio")`.

### `main.py`
- Thin entry: `from server import main; main()` (target of `[project.scripts]`).

## 6. Tool Surface

Nine tools, full read-only catalog. `top-10-tracks` endpoints folded into their parents to keep
the surface lean and cut round-trips.

| Tool | Endpoint(s) | Returns |
|---|---|---|
| `search(query, type="tracks", page=1, per_page=25)` | `GET /catalog/search/` | Compact hit list; type ∈ tracks/artists/releases/labels/charts; each line led by ID |
| `list_tracks(genre_id?, bpm_min?, bpm_max?, key?, artist_id?, label_id?, order_by?, page=1, per_page=25)` | `GET /catalog/tracks/` | Filtered/sorted browse — discovery workhorse |
| `get_track(track_id)` | `GET /catalog/tracks/{id}/` | Full track: BPM, key (+Camelot), genre, length, label, release, artists, preview |
| `get_artist(artist_id)` | `…/artists/{id}/` + `…/top-10-tracks/` | Artist info + top tracks |
| `get_release(release_id)` | `…/releases/{id}/` | Release info + tracklist |
| `get_label(label_id)` | `…/labels/{id}/` + `…/top-10-tracks/` | Label info + top tracks |
| `list_genres()` | `…/genres/` | id + name list (resolve genre name → id for filtering) |
| `get_genre(genre_id)` | `…/genres/{id}/` + top tracks/releases | Genre + what's hot in it |
| `get_chart(chart_id)` | `…/charts/{id}/` | Chart + its tracks |

Defaults: `per_page=25`, max 100. Each tool has a clear docstring (drives the MCP schema).

### Response shape (example)
```
Track #12345678 — "Strobe" by deadmau5
Genre: Progressive House · BPM: 128 · Key: A min (Camelot 8A) · Length: 10:33
Label: mau5trap · Release: For Lack of a Better Name (2009-09-22)
Preview: https://geo-samples.beatport.com/...
```
List tools emit one compact line per hit (`#id — title · artist · BPM · key`).

## 7. Auth & Token Lifecycle

Browser-based login is the **primary, user-facing auth path** — it is how a user makes the
server work. There is no expectation that an end user hand-copies tokens.

- **Bootstrap (`beatport-auth` CLI → `auth.py`, one-time):** the user runs the command; it opens
  the browser to `/auth/o/authorize`, the user logs into Beatport and authorizes, a localhost
  callback captures the `code`, it is exchanged at `/auth/o/token/`, and the resulting
  `ACCESS_TOKEN`/`REFRESH_TOKEN` (+ `CLIENT_ID`) are persisted to the token file. Exposed as a
  `[project.scripts]` entry alongside `beatport-mcp`.
- **Runtime (`beatport-mcp`):** seed from env / token file → Bearer on every call → on `401`,
  refresh (needs `client_id`) and retry once → persist rotated tokens to file.
- **Feasibility gate (verify-live):** the browser flow needs a `client_id` + a `redirect_uri`
  Beatport accepts. With no self-serve app registration, whether a loopback redirect is
  whitelisted is unknown (§11 #1, #7). The current working token was grabbed from devtools; that
  devtools capture is an **internal stopgap for our verification only — not the shipped UX.** If a
  loopback redirect is rejected, we adapt the capture mechanism while preserving the
  browser-login UX.

## 8. Data Flow

```
tool → client._request(path, params)
     → attach Bearer + Accept
     → httpx GET
     → [401? → TokenStore.refresh() → retry once]
     → JSON → transform.format_x() → readable string
     → tool returns string
```

## 9. Error Handling

Tools **return** error strings; they never raise into the MCP. A single `_handle()` helper maps:
- `401` after a refresh attempt → "Authentication failed — re-run the bootstrap / refresh your token."
- `404` → friendly not-found with the entity/id.
- `429` → surface `Retry-After`.
- Timeouts / network errors (`httpx` exceptions) → `Error: …`.
- Invalid params (e.g. `per_page > 100`) → clamped, or a clear message for bad enums.

## 10. Testing Strategy

- `test_transform.py` — pure unit tests on every formatter + the Camelot table, using **real
  captured fixtures**. No network.
- `test_client.py` — `respx`-mocked httpx: assert URL/params/bearer construction, the
  401→refresh→retry path, pagination clamping, and error mapping.
- `tests/fixtures/` — real JSON captured from live calls (sanitized of any tokens/PII).
- A separate **manual smoke script** verifies live endpoints/params; **kept out of CI** so no
  secrets ever touch CI.
- Run: `uv run pytest`; `ruff check` + `pyright` gate pre-merge.

## 11. Live-Verification Checklist (requires user's token in local `.env`)

Confirm against the real API before merge; capture fixtures as we go:
1. **`client_id`** — identify from devtools `POST /auth/o/token/` payload (required for refresh).
2. **Refresh-token rotation** — does Beatport rotate on refresh? (Decides token-file necessity.)
3. **`list_tracks` filter params** — exact names: `bpm` vs `bpm_gte/bpm_lte`, `key`/`key_id`,
   `genre_id`, valid `order_by` values.
4. **Key object shape** — does the track `key` already include Camelot? (Pass-through vs lookup.)
5. **Endpoint existence/paths** — confirm `top-10-tracks`, genre `top-10-releases`, chart, search
   `type` enum, and any list endpoints (`/catalog/releases/`, `/catalog/charts/`).
6. **Pagination envelope** — response keys (`results`/`count`/`next`) for the pagination helper.
7. **PKCE `redirect_uri`** — whether a loopback redirect works with the available client_id.

## 12. Contribution Mechanics

- Fork `larsenweigle/beatport-mcp`; set `upstream` = Larsen's, `origin` = fork.
- Feature branch `feat/catalog-tools`; conventional commits.
- PR to `larsenweigle/beatport-mcp:main` with setup notes (env vars, scripts) and a screenshot of
  Claude using the tools.
- Secrets live only in local `.env` (gitignored) and never enter git or CI.

## 13. Future (out of scope here)

- Personal-library tools (`/my/account`, `/my/beatport/tracks/`) + full user OAuth consent.
- Optional opinionated DJ layer (harmonic neighbors / set-building) as clearly-separate tools.
- Resources/prompts if useful (e.g. a genre-id reference resource).

## 14. Risks / Open Questions

- **Access fragility:** without a registered OAuth app, `client_id` may be a scraped/public value;
  ToS and longevity risk. Documented, not solved here.
- **Contract drift:** community-sourced contracts may differ from live; §11 mitigates before merge.
- **Upstream divergence:** Larsen commits daily; rebase on `upstream/main` before opening the PR.
