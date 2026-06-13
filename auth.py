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
        # The persisted file holds the live (possibly rotated) tokens, so it wins once it
        # exists; the provided access/refresh values only seed the very first run. To reset
        # credentials, delete the token file or re-run `beatport-auth`.
        saved = self._load()
        self.access_token = saved.get("access_token") if saved else access_token
        self.refresh_token = saved.get("refresh_token") if saved else refresh_token

    def _load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text())
        except (OSError, ValueError):
            return None  # unreadable/corrupt token file -> fall back to the seed

    @classmethod
    def from_env(cls) -> TokenStore:
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
        payload = json.dumps(
            {"access_token": self.access_token, "refresh_token": self.refresh_token}
        )
        # Create with owner-only perms from the start (no default-umask window); the chmod
        # afterwards also tightens a pre-existing file that had looser permissions.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(payload)
        self.path.chmod(0o600)


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
    code_box: dict[str, list[str]] = {}
    got_code = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in parsed:
                code_box.update(parsed)
                got_code.set()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorized. You can close this tab.")

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    server = http.server.HTTPServer(("localhost", 8765), Handler)

    def serve() -> None:
        while not got_code.is_set():
            server.handle_request()
        server.server_close()

    threading.Thread(target=serve, daemon=True).start()
    webbrowser.open(build_authorize_url(client_id, REDIRECT_URI, challenge))
    print("Waiting for browser authorization...")
    if not got_code.wait(timeout=120):
        raise SystemExit("Timed out waiting for browser authorization.")
    code = code_box["code"][0]
    resp = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
    }, timeout=30.0)
    resp.raise_for_status()
    tokens = resp.json()
    store = TokenStore(client_id=client_id)
    store.update(tokens["access_token"], tokens.get("refresh_token"))
    print(f"CLIENT_ID={client_id}")
    print(f"ACCESS_TOKEN={tokens['access_token']}")
    print(f"REFRESH_TOKEN={tokens.get('refresh_token')}")
    print(f"Tokens persisted to {store.path}")
