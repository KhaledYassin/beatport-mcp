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


class _CatalogClient:
    async def list_tracks(self, **kw):
        self.last = kw
        return {
            "results": [{"id": 1, "name": "T", "artists": [{"name": "A"}]}],
            "page": "1/1",
            "count": 1,
        }

    async def genres(self, per_page=100):
        return {"results": [{"id": 14, "name": "Melodic House & Techno"}]}

    async def artist(self, artist_id):
        return {"id": artist_id, "name": "deadmau5"}

    async def artist_tracks(self, artist_id, per_page=25):
        return {
            "results": [{"id": 2, "name": "Strobe", "artists": [{"name": "deadmau5"}]}],
            "count": 1,
        }

    async def release(self, release_id):
        return {"id": release_id, "name": "R", "artists": [{"name": "A"}]}

    async def release_tracks(self, release_id, per_page=25):
        return {"results": [{"id": 3, "name": "Trk", "artists": [{"name": "A"}]}], "count": 1}

    async def label(self, label_id):
        return {"id": label_id, "name": "mau5trap"}

    async def label_releases(self, label_id, per_page=25):
        return {
            "results": [{"id": 4, "name": "Rel", "artists": [{"name": "A"}], "track_count": 2}],
            "count": 1,
        }

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
