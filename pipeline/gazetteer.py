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
GAZETTEER_GEONAMES = GAZETTEER.parent / "gazetteer_geonames.csv"   # ticket 31, made by pipeline.gazetteer_geonames
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
                           r"hoang sa|truong sa|kalayaan|panatag|masinloc|"
                           # one-word names of single features, distinctive in this sea (ticket 34)
                           r"thitu|pag-?asa|triton|panata)\b", re.I)
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
def load(gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA, geonames: Path | None = None) -> dict[str, dict]:
    """feature_id -> row: the GeoNames extension (ticket 31), then the extra file, each replacing or adding
    rows. The GeoNames file is the one beside `gazetteer` unless another (or None, to leave it out) is given."""
    feats = {r["feature_id"]: r for r in _read(gazetteer)}
    if geonames is None and gazetteer == GAZETTEER:
        geonames = GAZETTEER_GEONAMES
    overlays = [geonames] if geonames is not None and Path(geonames).exists() else []
    for r in [row for path in overlays for row in _read(path)] + list(_read(extra)):
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
    feats = _merge_duplicates(feats)
    for r in feats.values():
        r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
        r["subregion"] = int(r["subregion"]) if r["subregion"] and r["subregion"] != "-" else None   # "-" = spans several
        r["names"] = sorted({r[c] for c in NAME_COLUMNS if r[c]} | {a for a in r["aliases"].split("|") if a})
    return feats


def _merge_duplicates(feats: dict[str, dict]) -> dict[str, dict]:
    """A row whose kind is "=<feature_id>" is a duplicate of that feature (Wikidata keeps some reefs twice,
    once under the Chinese name only): its names become the other's aliases and it leaves the map."""
    for fid in [f for f, r in feats.items() if r["kind"].startswith("=")]:
        dup = feats.pop(fid)
        target = feats[dup["kind"][1:]]
        names = {dup[c] for c in NAME_COLUMNS if dup[c]} | {a for a in dup["aliases"].split("|") if a}
        own = {target[c] for c in NAME_COLUMNS}
        target["aliases"] = "|".join(sorted({a for a in target["aliases"].split("|") if a} | (names - own)))
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
        if precision in ("unknown", "feature", "point"):
            event["location_precision"] = "subregion" if event.get("subregion") else "unknown"
        return event
    event["lat"], event["lon"] = f"{feat['lat']:.5f}", f"{feat['lon']:.5f}"
    sr = feat["subregion"] or subregion_of(feat["lat"], feat["lon"])
    event["subregion"] = str(sr) if sr else event.get("subregion", "")
    event["location_precision"] = "feature"   # the coordinates are the feature's, never the event's own
    return event


@lru_cache(maxsize=4)
def _index_once(gazetteer: Path, extra: Path):
    return _index(gazetteer, extra), load(gazetteer, extra)


def named_features(text: str, gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> list[dict]:
    """Every feature `text` names that is a point, in order of first mention (ticket 27: a move's reefs,
    shoals and islands on the map). An island group is an area, not a point, and is left out; a name
    shared by several features and the primary name of none is skipped; a longer name covers the
    shorter names inside it, so "Spratly Islands" never yields "Spratly Island"."""
    if not text or not text.strip():
        return []
    index, feats = _index_once(gazetteer, extra)
    folded = _fold(text)
    taken: list[tuple[int, int]] = []
    found: list[tuple[int, str]] = []
    for name, fids in index:
        start = 0
        while True:
            sub = folded[start:]
            pos = _find(name, sub)
            if pos < 0:
                break
            pos += start
            start = pos + len(name)
            if any(a <= pos < b or a < pos + len(name) <= b for a, b in taken):
                continue
            taken.append((pos, pos + len(name)))
            if len(fids) == 1 and feats[fids[0]]["kind"] != "island group" and feats[fids[0]]["lat"]:
                found.append((pos, fids[0]))
    out, seen = [], set()
    for _, fid in sorted(found):
        if fid not in seen:
            seen.add(fid)
            out.append(feats[fid])
    return out


# A name the maps can show: Latin letters, no pinyin or Vietnamese feature word (ticket 32). Degrees,
# minutes and dashes are punctuation, not another script.
NOT_ENGLISH = re.compile(r"\b(jiao|tan|dao|ansha|shazhou|qundao|qunjiao|lianjiao|sha|yu|chiao|tao|da|bai|banc|recif|zhudao|"
                         r"xisha|nansha|dongsha|zhongsha|hsisha|tungsha|shisha|chungsha|nan-sha|hsi-sha|truong sa|hoang sa)\b"
                         r"|[^\x00-\x7f’‘“”–—°′″·]", re.I)
# collective names that are no single feature
TERMS = {"Nanhai Zhudao": "South China Sea Islands", "Nanhai Islands": "South China Sea Islands",
         "Biển Đông": "South China Sea", "Nanhai": "South China Sea", "Laut Natuna Utara": "North Natuna Sea"}


# pinyin names that are also the established English ones (English Wikipedia's titles)
ENGLISH_AS_IS = {"Zhongsha Islands"}


def is_english_name(name: str) -> bool:
    return bool(name and name.strip()) and (name.strip() in ENGLISH_AS_IS or not NOT_ENGLISH.search(name))


GENERIC = r"(?:Islands?|Islets?|Reefs?|Shoals?|Banks?|Cays?|Atolls?|Patch(?:es)?|Rocks?|archipelagos?|groups?|Island Group)"
_NOT_A_NAME = re.compile(r"\b(near|off|around|about|north|south|east|west|northern|southern|eastern|western|central|"
                         r"eez|sea|waters|strait|basin|province|regency|city|district|fir|base|airbase|indonesian|malaysian|"
                         r"philippine|vietnamese|chinese|taiwanese|bruneian|national|park)\b", re.I)


@lru_cache(maxsize=4)
def _exact(gazetteer: Path, extra: Path) -> dict[str, str]:
    """folded name -> feature_id, for names that belong to one feature only."""
    index, _ = _index_once(gazetteer, extra)
    return {n: fids[0] for n, fids in index if len(fids) == 1}


def _feature_of(name: str, gazetteer: Path, extra: Path) -> str | None:
    name = name.strip().strip("'’\"")
    return _exact(gazetteer, extra).get(_fold(name)) if name else None


# names in brackets that say where, not which feature: never taken for another name of it
_PLACES_NOT_FEATURES = {_fold(n) for n in ["China", "Vietnam", "Philippines", "Malaysia", "Brunei", "Indonesia", "Taiwan",
    "PRC", "ROC", "Sabah", "Sarawak", "Palawan", "Zambales", "Hainan", "Borneo", "North Borneo", "Luzon", "Natuna", "Riau",
    "Sansha", "Kalayaan", "West Philippine Sea", "East Sea", "North Natuna Sea", "South China Sea", "Malaysian EEZ", "EEZ"]}


def english_place(text: str, gazetteer: Path = GAZETTEER, extra: Path = GAZETTEER_EXTRA) -> str:
    """A place as the maps and the review records show it, in English (tickets 32, 41). Two rules, nothing
    more, so the source's own words stay where they are:
    1. a name with another name of the same feature in brackets becomes the feature's English name:
       "Huangyan Dao (Scarborough Shoal)", "Bajo de Masinloc (Scarborough Shoal, Huangyan Dao)" and
       "Pag-asa (Thitu) Island" -> "Scarborough Shoal", "Scarborough Shoal", "Thitu Island";
    2. a name in another script or in pinyin or Vietnamese ("Nansha Qundao", "仁爱礁", "Đá Ba Đầu")
       becomes the English name of the one feature it names.
    Latin-script local names (Natuna, Kalayaan, Ayungin) are kept as written unless rule 1 applies."""
    if not text or not text.strip():
        return text
    feats = load(gazetteer, extra)

    def fid_of(n, g):
        """The one feature `n` names (with the generic after the bracket, if that makes a name); after
        "archipelago" or "group" only an island group counts ("Hoang Sa (Paracel) archipelago")."""
        group = g.lower() in ("archipelago", "archipelagos", "group", "groups", "island group", "islands")
        tries = [n + " " + g] if g else []
        tries += [n + " Islands", n] if group else [n]
        for t in tries:
            f = _feature_of(t, gazetteer, extra)
            if f and (not group or feats[f]["kind"] == "island group"):
                return f
        return None

    def name_like(n):   # capitalised words, the shape of a name
        return bool(re.fullmatch(r"[^\W\d_a-z][\w'’\-]*(?: [^\W\d_a-z][\w'’\-]*){0,3}", n))

    def bare_name(n):   # a proper name that is no feature, country or province ("Da Lat", "Ligaw")
        return name_like(n) and _fold(n) not in _PLACES_NOT_FEATURES and not _NOT_A_NAME.search(n)

    def same(m):
        raw, inner, g = m.group(1), m.group(2), m.group(3) or ""
        pad, words = raw[:len(raw) - len(raw.lstrip())], raw.strip().split(" ")
        parts = [q.strip() for q in re.split(r"\s*[,/;]\s*", inner) if q.strip()]
        if parts and all(q.casefold() in raw.casefold() for q in parts):   # "Thitu Island and Sandy Cay (Thitu Island, Sandy Cay)"
            return raw + (" " + g if g else "")
        if any(q.casefold() == raw.strip().casefold() for q in parts):   # "X (X, WPP 711)" -> "X (WPP 711)"
            rest = [q for q in parts if q.casefold() != raw.strip().casefold()]
            return raw + (" (" + ", ".join(rest) + ")" if rest else "") + (" " + g if g else "")
        for k in range(len(words)):   # the name is the end of what comes before: "near Woody Island (Yongxing Dao)"
            if k and not (words[k - 1][:1].islower() or words[k - 1].endswith(":") or
                          words[k - 1].lower() in ("near", "off", "around", "about", "at", "incl.")):
                continue   # never inside a run of capitalised words: "Beting Patinggi Ali" stays whole
            x, lead = " ".join(words[k:]).strip(), pad + " ".join(words[:k]) + (" " if k else "")
            if not x:
                continue
            sides = [x] + parts
            fids = [fid_of(n, g) for n in sides]
            found = {f for f in fids if f}
            if len(found) > 1:
                break   # two different features: "Luconia Shoals (South Luconia Shoals)" says both
            ok = lambda f, n, alone: f or (alone and bare_name(n)) or (not is_english_name(n) and (name_like(n) or not re.search(r"[A-Za-z]", n)))
            if len(found) == 1 and all(ok(f, n, i == 0 or len(parts) == 1) for i, (f, n) in enumerate(zip(fids, sides))):
                en = feats[next(iter(found))]["name_en"]
                if not en:
                    break
                tail = "" if not g or re.fullmatch(GENERIC, g, re.I) and re.search(GENERIC + r"$", en, re.I) else " " + g
                return lead + en + tail
        return m.group(0)
    bracketed = re.compile(r"([^(),;/]*?[^\s(),;/])\s*\(([^()]+)\)(?:\s+(" + GENERIC + r"))?(?![\w])", re.I)
    out = text
    for _ in range(2):
        out = bracketed.sub(same, out)
    # rule 2: names not in English, longest first
    names = sorted({(n, f["name_en"]) for f in feats.values() if f["name_en"] for n in f["names"]
                    if not is_english_name(n) and len(n) >= 3 and _feature_of(n, gazetteer, extra)} |
                   {(k, v) for k, v in TERMS.items()}, key=lambda t: -len(t[0]))
    group_names = {n for n, en in names if any(f["name_en"] == en and f["kind"] == "island group" for f in feats.values())}
    for n, en in names:   # not when a feature word follows ("Dongsha Island" is not "Pratas Islands Island"),
        # unless the name is an island group's and the word is "archipelago(s)" or "islands"
        if n in group_names:
            out = re.sub(r"(?<![\w'’])" + re.escape(n) + r"(?:\s+(?:archipelagos?|islands|group))?(?![\w'’])(?!\s+" + GENERIC + r"\b)",
                         en, out, flags=re.I)
        out = re.sub(r"(?<![\w'’])" + re.escape(n) + r"(?![\w'’])(?!\s+" + GENERIC + r"\b)", en, out, flags=re.I)
    out = re.sub(r"\b(?:Pulau|Terumbu)/(?=[A-Z])", "", out)   # "Pulau/Terumbu Layang-Layang" written both ways
    out = bracketed.sub(same, out)   # a bracket the translations made repeat itself
    kept = []   # a list that names a feature twice keeps it once
    for seg in re.split(r"(\s*[;/]\s*|,\s+)", out):
        if seg and kept and not re.fullmatch(r"\s*[;/]\s*|,\s+", seg) and seg.strip().casefold() in {k.strip().casefold() for k in kept[::2]}:
            if kept and re.fullmatch(r"\s*[;/]\s*|,\s+", kept[-1]):
                kept.pop()
            continue
        kept.append(seg)
    return re.sub(r"\s{2,}", " ", "".join(kept)).strip()
