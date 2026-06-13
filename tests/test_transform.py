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
    lines = out.splitlines()
    assert lines[0].startswith("#")
    assert lines[-1].startswith("Page ")        # pagination footer
    assert all(line.startswith("#") for line in lines[:-1])


def test_format_search_results_includes_pagination_footer():
    data = {"tracks": [TRACK], "page": "1/1035", "count": 3103}
    out = transform.format_search_results(data, "tracks")
    assert out.splitlines()[-1] == "Page 1/1035 · 3103 results"
