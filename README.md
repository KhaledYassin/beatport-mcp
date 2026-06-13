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

> More catalog tools (artists, releases, labels, genres, charts, and filtered browsing by
> BPM/key/genre) are on the roadmap.

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
`ACCESS_TOKEN`, and `REFRESH_TOKEN`. The server auto-refreshes the access token when it
expires.

> **Note:** Beatport does not currently offer self-serve API app registration, so the
> `client_id` and redirect URI used by the browser flow may need adjusting for your account.
> As an interim, you can copy `CLIENT_ID`, `ACCESS_TOKEN`, and `REFRESH_TOKEN` from your
> browser devtools — the `POST /auth/o/token/` request while signed in to Beatport — into the
> config below.

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
