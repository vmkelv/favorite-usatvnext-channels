"""Build the Favorites catalog and the extra stream files.

Channels are looked up by name in the main addon's catalog.

favorites.txt lists the channels of the Favorites row, in display order. Only
the tile fields are copied: Stremio asks the main addon for the rest when a
channel is opened.

streams.m3u lists extra streams for any channel of the main addon. Stremio
shows them next to the main addon's own streams.

    python3 build.py                  # read the published main catalog
    python3 build.py path/to/all.json # read a local copy instead
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FAVORITES_PATH = BASE_DIR / "favorites.txt"
STREAMS_PATH = BASE_DIR / "streams.m3u"
CATALOG_PATH = BASE_DIR / "catalog" / "tv" / "favorites.json"
STREAM_DIR = BASE_DIR / "stream" / "tv"
MAIN_CATALOG_URL = "https://raw.githubusercontent.com/scampari/usa-tv-next/main/catalog/tv/all.json"
TILE_FIELDS = ("id", "type", "name", "poster", "logo", "genres")


def normalize(name: str) -> str:
    return " ".join(name.split()).casefold()


def load_main_catalog(source: str | None) -> list[dict]:
    if source:
        return json.loads(Path(source).read_text())["metas"]
    with urllib.request.urlopen(MAIN_CATALOG_URL, timeout=30) as response:
        return json.load(response)["metas"]


def load_favorites() -> list[str]:
    lines = (line.strip() for line in FAVORITES_PATH.read_text().splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def load_streams() -> list[tuple[str, str]]:
    """Return (channel name, url) pairs from streams.m3u."""
    if not STREAMS_PATH.exists():
        return []
    pairs, name = [], ""
    for line in STREAMS_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            name = line.rpartition(",")[2].strip()
        elif line and not line.startswith("#"):
            pairs.append((name, line))
            name = ""
    return pairs


def main() -> int:
    channels = {normalize(c["name"]): c for c in load_main_catalog(sys.argv[1] if len(sys.argv) > 1 else None)}
    unknown: list[str] = []

    metas = []
    for name in load_favorites():
        channel = channels.get(normalize(name))
        if channel is None:
            unknown.append(name)
            continue
        tile = {field: channel[field] for field in TILE_FIELDS if channel.get(field)}
        if tile not in metas:
            metas.append(tile)

    streams: dict[str, list[dict]] = {}
    for name, url in load_streams():
        channel = channels.get(normalize(name))
        if channel is None:
            unknown.append(name or url)
            continue
        entries = streams.setdefault(channel["id"], [])
        if all(entry["url"] != url for entry in entries):
            entries.append({
                "url": url,
                "behaviorHints": {"notWebReady": True},
                "name": "Extra",
                "description": "My sources",
            })

    if unknown:
        print("Not in the main catalog: " + ", ".join(unknown), file=sys.stderr)
        return 1

    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps({"metas": metas}, separators=(",", ":")))
    print(f"Wrote {len(metas)} channels to {CATALOG_PATH.relative_to(BASE_DIR)}")

    # The stream files are all derived from streams.m3u, so a channel that is
    # no longer listed there loses its file.
    STREAM_DIR.mkdir(parents=True, exist_ok=True)
    for stale in STREAM_DIR.glob("*.json"):
        if stale.stem not in streams:
            stale.unlink()
    for channel_id, entries in streams.items():
        (STREAM_DIR / f"{channel_id}.json").write_text(json.dumps({"streams": entries}, separators=(",", ":")))
    total = sum(len(entries) for entries in streams.values())
    print(f"Wrote {total} extra streams for {len(streams)} channels to {STREAM_DIR.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
