"""Manual live probe — NOT run in CI. Requires CLIENT_ID/ACCESS_TOKEN/REFRESH_TOKEN
in the environment (load a local .env). Captures real JSON fixtures and prints a
compact contract summary.

Usage: set -a; source .env; set +a; uv run python scripts/verify.py [track_id]
"""

import asyncio
import json
import sys
from pathlib import Path

from auth import TokenStore
from client import BeatportClient


def _items(payload: dict) -> list:
    return (payload.get("results")
            or payload.get("data")
            or payload.get("tracks")
            or [])


async def main() -> None:
    client = BeatportClient(TokenStore.from_env())

    search = await client.search("strobe", type="tracks", per_page=3)
    print("=== SEARCH top-level keys ===")
    print(list(search.keys()))
    items = _items(search)
    print(f"=== SEARCH item count: {len(items)} ===")
    if items:
        print("=== first search item keys ===")
        print(sorted(items[0].keys()))

    track_id = int(sys.argv[1]) if len(sys.argv) > 1 else (items[0]["id"] if items else None)
    if track_id is None:
        print("No track id available — cannot probe track endpoint.")
        return

    track = await client.track(track_id)
    print(f"=== TRACK {track_id} top-level keys ===")
    print(sorted(track.keys()))
    print("=== TRACK key object ===")
    print(json.dumps(track.get("key"), indent=2))
    print("=== preview-ish fields present ===")
    print([k for k in track if "sample" in k.lower() or "preview" in k.lower() or "url" in k.lower()])
    print("=== release sub-keys ===")
    print(sorted((track.get("release") or {}).keys()))

    fixtures = Path("tests/fixtures")
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "track.json").write_text(json.dumps(track, indent=2))
    (fixtures / "search_tracks.json").write_text(json.dumps(search, indent=2))
    print("=== wrote tests/fixtures/track.json and search_tracks.json ===")


if __name__ == "__main__":
    asyncio.run(main())
