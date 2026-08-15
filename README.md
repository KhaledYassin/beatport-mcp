# beatport-mcp

An [MCP](https://modelcontextprotocol.io/introduction) server for the [Beatport v4 API](https://api.beatport.com/v4/docs/) — read-only catalog access for LLM agents like Claude.

It exposes the Beatport catalog as MCP tools with clean, LLM-friendly responses. Track
data is enriched with neutral [Camelot / Open-Key](https://mixedinkey.com/camelot-wheel/)
notation alongside Beatport's own musical key — handy for DJs, while the responses stay
faithful to the API for any consumer.

## Tools

| Tool | Description |
|------|-------------|
| `search(query, type="tracks", page=1, per_page=25)` | Search the catalog. `type` is one of `tracks`, `artists`, `releases`, `labels`, `charts`. Each result line is led by its ID. |
| `get_track(track_id)` | Full track details: title, artists, BPM, key (with Camelot/Open-Key), genre, length, label, release, and preview URL. |
| `list_tracks(genre_id, artist_id, label_id, bpm, key, name, newest_first, page, per_page)` | Browse/filter tracks. `key` takes a name like `"A minor"`; `bpm` is exact (the API has no range — call several values to cover one). Sorts by release date. |
| `list_genres()` | All Beatport genres with their IDs. |
| `get_artist(artist_id)` | Artist profile plus their most recent tracks. |
| `get_release(release_id)` | Release details plus its full tracklist. |
| `get_label(label_id)` | Label profile plus its most recent releases. |
| `get_genre(genre_id)` | Genre details plus its most recent tracks. |
| `get_chart(chart_id)` | Chart details plus its tracks. |

## Set Up

### 1. Prerequisites

Install [uv](https://docs.astral.sh/uv/), then from the project directory:

```bash
uv sync
```

### 2. Authenticate

The server talks to Beatport with an OAuth access/refresh token. Run the one-time browser
login:

```bash
uv run beatport-auth
```

This opens your browser to sign in to Beatport, then persists and prints your `CLIENT_ID`,
`ACCESS_TOKEN`, and `REFRESH_TOKEN`.

Refreshed access tokens last 10 hours; `BeatportClient` refreshes on any `401` and persists the
result, so the server keeps itself alive without further attention.

> **Note:** Beatport does not currently offer self-serve API app registration, so the
> `client_id` and redirect URI used by the browser flow may need adjusting for your account.
> If the browser login fails, grab credentials by hand instead:
>
> 1. Sign in at **`https://api.beatport.com/v4/docs/`** and copy the JSON from the token
>    response (devtools → Network). It contains `access_token` and `refresh_token`.
> 2. You do **not** need to hunt for a separate `client_id`: the access token is a JWT whose
>    payload contains a `client_id` claim. Decode its middle segment to read it, e.g.
>    `python -c "import base64,json,sys; p=sys.argv[1].split('.')[1]; p+='='*(-len(p)%4); print(json.loads(base64.urlsafe_b64decode(p))['client_id'])" <access_token>`
> 3. Put all three in `.env` (gitignored) or in the config below.
>
> **Use the docs app, not the store frontend.** `https://www.beatport.com/api/auth/session`
> also returns an `accessToken`/`refreshToken` pair, and the access token works fine for
> catalog reads — but its refresh token is bound to a client the store's server-side session
> holds, so refreshing with it always fails `400 {"error": "invalid_grant"}` and you are left
> with a credential that dies in 10 minutes and cannot renew. Tokens from the docs app carry
> scope `app:docs` and refresh correctly; store tokens carry `app:prostore` and do not.
>
> Take the `client_id` from **the same token you are pasting** — a refresh sends `client_id`
> and `refresh_token` together, so the two must come from one app. The error codes tell you
> which half is wrong: `400 invalid_grant` = refresh token stale, spent, or from another
> client; `401 invalid_client` = `client_id` missing or unknown.

> **Gotcha:** the persisted token file (`~/.beatport-mcp/token.json`, override with
> `BEATPORT_TOKEN_PATH`) takes precedence over the environment — env values only seed the
> very first run. After pasting fresh credentials, delete that file, or the server will keep
> using the old ones and fail with *"Authentication failed"*.

> **Refresh tokens are single-use.** Beatport rotates the refresh token on every exchange and
> revokes the old one immediately, which is why the token file exists: the credentials in your
> environment are a one-shot seed and go stale after the first refresh. Two consequences —
> don't expect the `.env` values to keep working, and don't point two clients at the same token
> file (give scripts their own via `BEATPORT_TOKEN_PATH`), since whichever refreshes first
> strands the other.

### 3. Register the server with Claude

Locate your `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%/Claude/claude_desktop_config.json`

Add the `beatport` server (replace the path and credentials):

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

Restart Claude Desktop. You can then ask things like *"Search Beatport for Strobe"* or
*"Get details for Beatport track 19431036"*.

## Development

```bash
uv run pytest        # run the test suite
uv run ruff check .  # lint
uv run pyright       # type-check
```
