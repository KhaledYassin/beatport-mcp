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
    assert track.calls[1].request.headers["Authorization"] == "Bearer new"  # retry uses new token


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


@respx.mock
async def test_failed_refresh_raises_friendly_error(tmp_path):
    respx.get("https://api.beatport.com/v4/catalog/tracks/1/").mock(
        return_value=httpx.Response(401)
    )
    respx.post("https://api.beatport.com/v4/auth/o/token/").mock(
        return_value=httpx.Response(400, json={"error": "invalid_grant"})
    )
    client = BeatportClient(_store(tmp_path))
    with pytest.raises(BeatportError, match="Authentication failed"):
        await client.track(1)


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


@respx.mock
async def test_non_json_response_raises_beatport_error(tmp_path):
    respx.get("https://api.beatport.com/v4/catalog/tracks/1/").mock(
        return_value=httpx.Response(200, text="<html>oops</html>")
    )
    client = BeatportClient(_store(tmp_path))
    with pytest.raises(BeatportError, match="non-JSON"):
        await client.track(1)
