"""The gazetteer: named South China Sea features with coordinates and sub-region, and the two
operations built on it — resolving a location name written in a document to a feature, and finding
which MAVD sub-region a coordinate falls in.

Files: data/reference/gazetteer.csv (generated from Wikidata by pipeline.gazetteer_wikidata) and
data/reference/gazetteer_extra.csv (hand additions and corrections; same columns; a row with an
existing feature_id corrects it — blank fields keep the generated value, aliases are added, an alias
written as `-Name` is removed). Columns: feature_id, name_en, name_zh, name_vi,
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
# A name is used for matching only when it reads as a feature name: a Latin name must contain a
# feature word or have at least two words; a CJK name must have at least three characters. Wikidata
# aliases include ordinary words ("Kota", "Timog", "Rizal") that would otherwise place mainland news
# on a reef. Hand-added aliases follow the same rule.
FEATURE_WORDS = re.compile(r"\b(reefs?|shoals?|banks?|islands?|islets?|rocks?|cays?|atolls?|breakers|patch|tablemount|sand|"
                           r"jiao|dao|tan|ansha|shazhou|yu|qundao|qunjiao|huanjiao|"
                           r"da|bai|dao|con|cum|nui|rach|quan dao|"
                           r"bahura|pulo|kapuluan|buhanginan|beting|pulau|terumbu|gosong|kepulauan|"
                           # names that stand alone in prose
                           r"paracels?|spratlys?|xisha|nansha|zhongsha|dongsha|pratas|natuna|luconia|scarborough|ayungin|macclesfield|"
                           r"hoang sa|truong sa|kalayaan|panatag|masinloc)\b", re.I)
MIN_CJK = 3


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


@lru_cache(maxsize=4)
def _polygons(path: str = str(SUBREGIONS)) -> list[tuple[int, list]]:
    gj = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for f in gj["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        out.append((int(f["properties"]["LocationNo"]), polys))
    return out


def subregion_of(lat: float, lon: float, polygons: Path = SUBREGIONS) -> int | None:
    """The MAVD sub-region (1–10) containing the point, or None if it is outside all ten."""
    for n, polys in _polygons(str(polygons)):
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
            adds = {a for a in r["aliases"].split("|") if a and not a.startswith("-")}
            drops = {a[1:] for a in r["aliases"].split("|") if a.startswith("-")}
            merged["aliases"] = "|".join(sorted(({a for a in base["aliases"].split("|") if a} | adds) - drops))
            for c in NAME_COLUMNS:   # a dropped alias may also be a generated primary name
                if merged[c] in drops:
                    merged[c] = ""
            feats[r["feature_id"]] = merged
        else:
            feats[r["feature_id"]] = {k: r.get(k, "") for k in COLUMNS}
    for r in feats.values():
        r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
        r["subregion"] = int(r["subregion"]) if r["subregion"] and r["subregion"] != "-" else None   # "-" = spans several
        r["names"] = sorted({r[c] for c in NAME_COLUMNS if r[c]} | {a for a in r["aliases"].split("|") if a})
    return feats


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).replace("Đ", "D").replace("đ", "d")   # đ has no decomposition
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def _is_cjk(s: str) -> bool:
    return bool(re.search(r"[一-鿿]", s))


def usable_name(name: str) -> bool:
    """Whether a name is distinctive enough to match inside prose (see FEATURE_WORDS)."""
    if _is_cjk(name):
        return len(re.sub(r"[^一-鿿]", "", name)) >= MIN_CJK
    folded = _fold(name)
    return bool(FEATURE_WORDS.search(folded)) or len(folded.split()) >= 2


@lru_cache(maxsize=4)
def _index(gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> list[tuple[str, tuple[str, ...]]]:
    """(folded name, feature ids it names), longest names first. A name that belongs to several
    features (three "North Reef"s) keeps all of them; resolve() then prefers the feature whose
    primary name it is and otherwise refuses to choose."""
    by_name: dict[str, list[str]] = {}
    primary: dict[str, set[str]] = {}
    for fid, r in load(gazetteer, extra).items():
        for n in r["names"]:
            if not usable_name(n):
                continue
            by_name.setdefault(_fold(n), [])
            if fid not in by_name[_fold(n)]:
                by_name[_fold(n)].append(fid)
            if n in (r[c] for c in NAME_COLUMNS):
                primary.setdefault(_fold(n), set()).add(fid)
    pairs = []
    for name, fids in by_name.items():
        prim = [f for f in fids if f in primary.get(name, ())]
        pairs.append((name, tuple(prim) if len(prim) == 1 else tuple(fids)))
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs


def _find(name: str, folded: str) -> int:
    if _is_cjk(name):
        return folded.find(name)
    m = re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])", folded)
    return m.start() if m else -1


def _earliest(text: str, gazetteer: Path, extra: Path):
    folded = _fold(text)
    best = None
    for name, fids in _index(gazetteer, extra):
        pos = _find(name, folded)
        if pos >= 0 and (best is None or (pos, -len(name)) < (best[0], best[1])):
            best = (pos, -len(name), fids)
    return best


def resolve(text: str, gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> dict | None:
    """The feature named earliest in `text` (longest name on a tie), or None: when the text names
    nothing usable, or when the earliest name belongs to several features and is the primary name
    of none of them (the reviewer decides). Latin names match on word boundaries; CJK anywhere."""
    if not text or not text.strip():
        return None
    best = _earliest(text, gazetteer, extra)
    if best is None or len(best[2]) != 1:
        return None
    return load(gazetteer, extra)[best[2][0]]


def ambiguous(text: str, gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> list[dict]:
    """The features an unresolvable name could mean (empty when it names nothing, or one thing)."""
    if not text or not text.strip():
        return []
    best = _earliest(text, gazetteer, extra)
    feats = load(gazetteer, extra)
    return [feats[f] for f in best[2]] if best and len(best[2]) > 1 else []


def locate(event: dict, gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> dict:
    """Place an event from what it carries, in this order of trust: its own coordinates (the
    sub-region then follows from the polygons, whatever was stated); else its location_name through
    the gazetteer (coordinates and sub-region from the feature, unless the precision says the event
    is only known to a sub-region; an island group gives a sub-region, never a point); else nothing.
    A stated sub-region that disagrees with coordinates is replaced, because the coordinates are the
    more specific claim and the validator holds the two together. Returns the (same) dict."""
    if event.get("lat") and event.get("lon"):
        try:
            sr = subregion_of(float(event["lat"]), float(event["lon"]))
        except (TypeError, ValueError):
            return event
        if sr:
            event["subregion"] = str(sr)
        return event
    feat = resolve(event.get("location_name", ""), gazetteer, extra)
    if feat is None:
        return event
    precision = event.get("location_precision") or "unknown"
    if feat["kind"] == "island group" or precision == "subregion":   # an area, not a point
        if not event.get("subregion") and feat["subregion"]:
            event["subregion"] = str(feat["subregion"])
        if precision == "unknown" and event.get("subregion"):
            event["location_precision"] = "subregion"
        return event
    event["lat"], event["lon"] = f"{feat['lat']:.5f}", f"{feat['lon']:.5f}"
    sr = feat["subregion"] or subregion_of(feat["lat"], feat["lon"])
    event["subregion"] = str(sr) if sr else event.get("subregion", "")
    if precision == "unknown":
        event["location_precision"] = "feature"
    return event
