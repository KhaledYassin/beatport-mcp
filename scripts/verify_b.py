"""Plan B live contract probe — NOT in CI. Reads CLIENT_ID from .env and uses the
valid persisted ~/.beatport-mcp/token.json (TokenStore with access_token=None loads it).
Discovers contracts for the remaining 7 catalog endpoints and captures fixtures.

Usage: uv run python scripts/verify_b.py
"""

import asyncio
import json
import pathlib

from auth import TokenStore
from client import BeatportClient, BeatportError

PROJ = pathlib.Path(__file__).resolve().parent.parent
FIX = PROJ / "tests" / "fixtures"
FIX.mkdir(parents=True, exist_ok=True)


def client_id() -> str:
    for line in (PROJ / ".env").read_text().splitlines():
        s = line.strip()
        if s.startswith("CLIENT_ID="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("CLIENT_ID missing from .env")


async def probe(client, path, params=None):
    try:
        return await client._request(path, params), None
    except BeatportError as e:
        return None, f"BeatportError: {e}"
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def topkeys(d):
    return sorted(d.keys()) if isinstance(d, dict) else f"<{type(d).__name__}>"


def count_of(d):
    return d.get("count") if isinstance(d, dict) else None


def items_of(d):
    if not isinstance(d, dict):
        return []
    for k in ("results", "data"):
        if isinstance(d.get(k), list):
            return d[k]
    # fall back: first list-valued key
    for v in d.values():
        if isinstance(v, list):
            return v
    return []


def save(name, data):
    (FIX / name).write_text(json.dumps(data, indent=2))
    print(f"  saved tests/fixtures/{name}")


async def main():
    store = TokenStore(client_id=client_id())  # access_token=None -> loads token.json
    client = BeatportClient(store)
    track = json.loads((FIX / "track.json").read_text())
    gid = track["genre"]["id"]
    rid = track["release"]["id"]
    aid = track["artists"][0]["id"]
    lid = track["release"]["label"]["id"]
    print("IDs:", dict(genre=gid, release=rid, artist=aid, label=lid))

    print("\n## list endpoint envelope (catalog/tracks/)")
    d, err = await probe(client, "catalog/tracks/", {"per_page": 3})
    print(" err:", err, "| keys:", topkeys(d), "| count:", count_of(d))
    if d:
        save("list_tracks.json", d)
        its = items_of(d)
        print(" list item-list key present; first item keys:", topkeys(its[0]) if its else None)

    print("\n## list_genres (catalog/genres/)")
    d, err = await probe(client, "catalog/genres/", {"per_page": 200})
    print(" err:", err, "| keys:", topkeys(d))
    if d:
        save("genres_list.json", d)
        its = items_of(d)
        print(" item count:", len(its), "| first item keys:", topkeys(its[0]) if its else None)

    print("\n## list_tracks FILTER param discovery")
    base, _ = await probe(client, "catalog/tracks/", {"per_page": 1})
    base_count = count_of(base)
    print(" baseline count:", base_count)
    candidates = {
        "genre_id": {"genre_id": gid},
        "genre": {"genre": gid},
        "artist_id": {"artist_id": aid},
        "label_id": {"label_id": lid},
        "bpm": {"bpm": 128},
        "bpm_gte/lte": {"bpm_gte": 120, "bpm_lte": 130},
        "bpm__gte/__lte": {"bpm__gte": 120, "bpm__lte": 130},
        "bpm_start/end": {"bpm_start": 120, "bpm_end": 130},
        "key_id": {"key_id": track["key"]["id"]},
        "ordering=-bpm": {"ordering": "-bpm"},
        "order_by=-bpm": {"order_by": "-bpm"},
        # extra guesses
        "min_bpm/max_bpm": {"min_bpm": 120, "max_bpm": 130},
        "bpm_low/high": {"bpm_low": 120, "bpm_high": 130},
        "genre_id(str)": {"genre_id": str(gid)},
        "genre_ids": {"genre_ids": gid},
        "genres": {"genres": gid},
        "sort": {"sort": "-bpm"},
        "order": {"order": "-bpm"},
    }
    for label, params in candidates.items():
        d, err = await probe(client, "catalog/tracks/", {**params, "per_page": 1})
        c = count_of(d)
        if err:
            verdict = "ERR " + err
        elif base_count and c is not None:
            verdict = f"count={c} " + ("(FILTERS)" if c < base_count else "(no change)")
        else:
            verdict = f"count={c}"
        print(f"  {label:16} -> {verdict}")

    print("\n## get_artist + top tracks")
    d, err = await probe(client, f"catalog/artists/{aid}/")
    print(" artist err:", err, "| keys:", topkeys(d))
    if d:
        save("artist.json", d)
    for sub in (f"catalog/artists/{aid}/top-10-tracks/",
                f"catalog/artists/{aid}/top-100-tracks/",
                f"catalog/artists/{aid}/tracks/"):
        d, err = await probe(client, sub, {"per_page": 3})
        print(f"  {sub} -> err:{err} keys:{topkeys(d) if d else None}")
        if d:
            save("artist_top_tracks.json", d)

    print("\n## get_release + tracks")
    d, err = await probe(client, f"catalog/releases/{rid}/")
    print(" release err:", err, "| keys:", topkeys(d))
    if d:
        save("release.json", d)
    d, err = await probe(client, f"catalog/releases/{rid}/tracks/", {"per_page": 5})
    print(" release tracks -> err:", err, "keys:", topkeys(d) if d else None)
    if d:
        save("release_tracks.json", d)

    print("\n## get_label + top tracks")
    d, err = await probe(client, f"catalog/labels/{lid}/")
    print(" label err:", err, "| keys:", topkeys(d))
    if d:
        save("label.json", d)
    for sub in (f"catalog/labels/{lid}/top-10-tracks/",
                f"catalog/labels/{lid}/top-100-tracks/",
                f"catalog/labels/{lid}/tracks/"):
        d, err = await probe(client, sub, {"per_page": 3})
        print(f"  {sub} -> err:{err} keys:{topkeys(d) if d else None}")
        if d:
            save("label_top_tracks.json", d)

    print("\n## get_genre + top tracks/releases")
    d, err = await probe(client, f"catalog/genres/{gid}/")
    print(" genre err:", err, "| keys:", topkeys(d))
    if d:
        save("genre.json", d)
    for sub in (f"catalog/genres/{gid}/top-100-tracks/",
                f"catalog/genres/{gid}/top-10-tracks/",
                f"catalog/genres/{gid}/top-100-releases/",
                f"catalog/genres/{gid}/top-10-releases/"):
        d, err = await probe(client, sub, {"per_page": 3})
        print(f"  {sub} -> err:{err} keys:{topkeys(d) if d else None}")

    print("\n## get_chart (discover an id first)")
    d, err = await probe(client, "catalog/charts/", {"per_page": 3})
    print(" charts list err:", err, "| keys:", topkeys(d))
    chart_id = None
    if d:
        its = items_of(d)
        if its:
            chart_id = its[0].get("id")
    print(" chart_id:", chart_id)
    if chart_id:
        d, err = await probe(client, f"catalog/charts/{chart_id}/")
        print(" chart err:", err, "| keys:", topkeys(d))
        if d:
            save("chart.json", d)
        d, err = await probe(client, f"catalog/charts/{chart_id}/tracks/", {"per_page": 5})
        print(" chart tracks -> err:", err, "keys:", topkeys(d) if d else None)
        if d:
            save("chart_tracks.json", d)


if __name__ == "__main__":
    asyncio.run(main())
