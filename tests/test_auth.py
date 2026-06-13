import base64
import hashlib
import json

import httpx
import pytest
import respx

from auth import TokenStore, build_authorize_url, pkce_pair, refresh_tokens


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


def test_from_env_raises_without_client_id(monkeypatch):
    monkeypatch.delenv("CLIENT_ID", raising=False)
    with pytest.raises(RuntimeError, match="CLIENT_ID"):
        TokenStore.from_env()


def test_pkce_pair_and_authorize_url():
    verifier, challenge = pkce_pair()
    assert 43 <= len(verifier) <= 128
    url = build_authorize_url(client_id="cid", redirect_uri="http://localhost:8765/callback",
                              challenge=challenge)
    assert url.startswith("https://api.beatport.com/v4/auth/o/authorize/?")
    assert "code_challenge_method=S256" in url
    assert "client_id=cid" in url
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    assert challenge == expected


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


def test_persisted_file_wins_over_seed(tmp_path):
    path = tmp_path / "token.json"
    path.write_text(json.dumps({"access_token": "fresh", "refresh_token": "fresh_r"}))
    # a stale env/explicit seed must not override the live persisted tokens
    store = TokenStore(client_id="cid", access_token="stale", refresh_token="stale_r", path=path)
    assert store.access_token == "fresh"
    assert store.refresh_token == "fresh_r"


def test_corrupt_token_file_falls_back_to_seed(tmp_path):
    path = tmp_path / "token.json"
    path.write_text("{ not json")
    store = TokenStore(client_id="cid", access_token="seed", path=path)
    assert store.access_token == "seed"
