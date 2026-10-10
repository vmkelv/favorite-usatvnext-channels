"""Build the Favorites catalog from favorites.txt.

Channels are looked up by name in the main addon's catalog and written in the
order they are listed. Only the tile fields are copied: streams stay with the
main addon, which Stremio asks when a channel is opened.

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
CATALOG_PATH = BASE_DIR / "catalog" / "tv" / "favorites.json"
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


def main() -> int:
    channels = {normalize(c["name"]): c for c in load_main_catalog(sys.argv[1] if len(sys.argv) > 1 else None)}

    metas, unknown = [], []
    for name in load_favorites():
        channel = channels.get(normalize(name))
        if channel is None:
            unknown.append(name)
            continue
        tile = {field: channel[field] for field in TILE_FIELDS if channel.get(field)}
        if tile not in metas:
            metas.append(tile)

    if unknown:
        print("Not in the main catalog: " + ", ".join(unknown), file=sys.stderr)
        return 1

    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps({"metas": metas}, separators=(",", ":")))
    print(f"Wrote {len(metas)} channels to {CATALOG_PATH.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
