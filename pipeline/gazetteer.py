"""The gazetteer: named South China Sea features with coordinates and sub-region, and the two
operations built on it — resolving a location name written in a document to a feature, and finding
which MAVD sub-region a coordinate falls in.

Files: data/reference/gazetteer.csv (generated from Wikidata by pipeline.gazetteer_wikidata) and
data/reference/gazetteer_extra.csv (hand additions and corrections; same columns; a row with an
existing feature_id corrects it — blank fields keep the generated value, aliases are added). Columns: feature_id, name_en, name_zh, name_vi,
name_fil, name_ms, aliases (| separated), lat, lon, subregion, kind, wikidata, retrieved.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "data" / "reference"
GAZETTEER = REFERENCE / "gazetteer.csv"
GAZETTEER_EXTRA = REFERENCE / "gazetteer_extra.csv"
SUBREGIONS = REFERENCE / "mavd_subregions.geojson"
COLUMNS = ["feature_id", "name_en", "name_zh", "name_vi", "name_fil", "name_ms", "aliases", "lat", "lon", "subregion", "kind", "wikidata", "retrieved"]
NAME_COLUMNS = ["name_en", "name_zh", "name_vi", "name_fil", "name_ms"]
MIN_NAME = 4   # shorter names (e.g. "Đá") match too much


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9一-鿿]+", "-", s).strip("-").lower()
    return s or "feature"


# ---------------------------------------------------------------------------
# sub-region from a coordinate

def _point_in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i][:2]
        x2, y2 = ring[i - 1][:2]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


@lru_cache(maxsize=1)
def _polygons(path: str = str(SUBREGIONS)) -> list[tuple[int, list]]:
    gj = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for f in gj["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        out.append((int(f["properties"]["LocationNo"]), polys))
    return out


def subregion_of(lat: float, lon: float) -> int | None:
    """The MAVD sub-region (1–10) containing the point, or None if it is outside all ten."""
    for n, polys in _polygons():
        for poly in polys:
            if _point_in_ring(lon, lat, poly[0]) and not any(_point_in_ring(lon, lat, hole) for hole in poly[1:]):
                return n
    return None


# ---------------------------------------------------------------------------
# features and name resolution

def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


@lru_cache(maxsize=4)
def load(gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> dict[str, dict]:
    """feature_id -> row, the extra file replacing or adding rows."""
    feats = {r["feature_id"]: r for r in _read(gazetteer)}
    for r in _read(extra):
        base = feats.get(r["feature_id"])
        if base:   # a correction: blank fields keep the generated value, aliases are added
            merged = {k: (r.get(k) or base.get(k, "")) for k in COLUMNS}
            merged["aliases"] = "|".join(sorted({a for a in (base["aliases"] + "|" + r["aliases"]).split("|") if a}))
            feats[r["feature_id"]] = merged
        else:
            feats[r["feature_id"]] = {k: r.get(k, "") for k in COLUMNS}
    for r in feats.values():
        r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
        r["subregion"] = int(r["subregion"]) if r["subregion"] and r["subregion"] != "-" else None   # "-" = spans several
        r["names"] = sorted({r[c] for c in NAME_COLUMNS if r[c]} | {a for a in r["aliases"].split("|") if a})
    return feats


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


@lru_cache(maxsize=4)
def _index(gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> list[tuple[str, str]]:
    """(folded name, feature_id), longest names first, so "Thitu Island" wins over "Thitu"."""
    pairs = []
    for fid, r in load(gazetteer, extra).items():
        for n in r["names"]:
            if len(n) >= MIN_NAME or re.search(r"[一-鿿]", n):
                pairs.append((_fold(n), fid))
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs


def resolve(text: str, gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> dict | None:
    """The feature named earliest in `text` (longest name on a tie), or None. Latin names must match on
    word boundaries; CJK names anywhere."""
    if not text or not text.strip():
        return None
    folded = _fold(text)
    best: tuple[int, int, str] | None = None
    for name, fid in _index(gazetteer, extra):
        if re.search(r"[一-鿿]", name):
            pos = folded.find(name)
        else:
            m = re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", folded)
            pos = m.start() if m else -1
        if pos >= 0 and (best is None or (pos, -len(name)) < (best[0], best[1])):
            best = (pos, -len(name), fid)
    return load(gazetteer, extra)[best[2]] if best else None


def locate(event: dict, gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> dict:
    """Fill an event's lat/lon/subregion/location_precision from its location_name when they are
    blank and the name resolves; never overwrites a value already present. Returns the (same) dict."""
    if event.get("lat") or event.get("lon"):
        if not event.get("subregion"):
            try:
                sr = subregion_of(float(event["lat"]), float(event["lon"]))
                event["subregion"] = str(sr) if sr else ""
            except (TypeError, ValueError):
                pass
        return event
    feat = resolve(event.get("location_name", ""), gazetteer, extra)
    if feat is None:
        return event
    if not event.get("subregion") and feat["subregion"]:
        event["subregion"] = str(feat["subregion"])
    blank = not event.get("location_precision") or event.get("location_precision") == "unknown"
    if feat["kind"] == "island group":   # "in the Spratlys" is an area, not a point
        if blank and event.get("subregion"):
            event["location_precision"] = "subregion"
        return event
    event["lat"], event["lon"] = f"{feat['lat']:.5f}", f"{feat['lon']:.5f}"
    if blank:
        event["location_precision"] = "feature"
    return event
