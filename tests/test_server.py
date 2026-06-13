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
