"""Extend the gazetteer from GeoNames (CC BY 4.0): more reefs, shoals, banks, islands and rocks inside
the ten MAVD sub-regions, and more names for the ones the Wikidata gazetteer already has (pinyin,
Vietnamese, Filipino and English variants), so that more move descriptions place on the map (ticket 31).

Writes data/reference/gazetteer_geonames.csv in the format of gazetteer_extra.csv: a row whose
feature_id is already in gazetteer.csv adds aliases to it; any other row is a new feature. The
loader applies it after gazetteer.csv and before gazetteer_extra.csv, so the project's own corrections
still win. Run by hand when it needs refreshing; the build and the validator never call GeoNames.

  python -m pipeline.gazetteer_geonames --dumps /tmp/gn/CN.zip /tmp/gn/VN.zip ... [--out data/reference/gazetteer_geonames.csv]

The country dumps come from https://download.geonames.org/export/dump/ (one zip per country code).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import math
import re
import sys
import zipfile
from functools import lru_cache
from pathlib import Path

from pipeline import gazetteer as gz

OUT = gz.GAZETTEER.parent / "gazetteer_geonames.csv"
# GeoNames feature codes for maritime features (class H, T and U)
CODES = {"RF": "reef", "RFC": "reef", "RFSU": "reef", "RFU": "reef", "RFX": "reef",
         "SHOL": "shoal", "SHOLS": "shoal", "SHLU": "shoal", "SHSU": "shoal", "BAR": "shoal",
         "BNK": "bank", "BNKS": "bank", "BNKU": "bank", "BNKX": "bank", "TMTU": "bank", "SMU": "bank",
         "ISL": "island", "ISLET": "island", "ISLF": "island", "ISLM": "island", "ISLT": "island",
         "ISLS": "island group", "ATOL": "atoll", "RK": "rock", "RKS": "rock"}
GENERIC = {"reef", "reefs", "shoal", "shoals", "bank", "banks", "island", "islands", "islet", "rock", "rocks", "cay",
           "atoll", "dao", "jiao", "tan", "ansha", "shazhou", "dá", "da", "bai", "bãi", "đá", "đảo", "dao", "north", "south",
           "east", "west", "the", "of", "and", "great", "little", "small", "big"}
MATCH_KM = 4.0      # a GeoNames feature this close to a gazetteer feature, sharing a name word, is the same one
NAME_KM = 60.0      # this close, sharing a whole name (pinyin included), it is the same one: GeoNames rounds some
                    # positions to a quarter degree, and full names like "Guangxingzai Jiao" are unique in the sea
# an English name: an English feature word, and no pinyin generic or non-ASCII letter
ENGLISH = re.compile(r"\b(reef|reefs|shoal|shoals|bank|banks|island|islands|islet|islets|cay|cays|rock|rocks|atoll|patch|"
                     r"patches|seamount|breakers|ledge|group|spit|sand|sands|knoll|tablemount|ridge)\b", re.I)
NOT_ENGLISH = re.compile(r"\b(jiao|tan|dao|ansha|shazhou|qunjiao|lianjiao|qundao|sha|yu|chiao|tao|banc|recif|bai|da|dao)\b|[^\x00-\x7f’]", re.I)
COLS = ["geonameid", "name", "asciiname", "alternatenames", "lat", "lon", "fclass", "fcode", "cc"]


def km(a_lat, a_lon, b_lat, b_lon) -> float:
    p = math.pi / 180
    x = (b_lon - a_lon) * p * math.cos((a_lat + b_lat) / 2 * p)
    return 6371 * math.hypot(x, (b_lat - a_lat) * p)


def words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", gz._fold(name)) if w not in GENERIC and len(w) > 2}


def is_english(name: str) -> bool:
    return bool(ENGLISH.search(name)) and not NOT_ENGLISH.search(name)


@lru_cache(maxsize=None)
def _keys(names: tuple[str, ...]) -> frozenset[str]:
    return frozenset(keys(names))


def keys(names) -> set[str]:
    """Whole-name keys: letters only, accents and spaces dropped, Chinese names also as pinyin, so that
    "Mahuan Dao", "Ma-huan Tao" is not but "马欢岛" is the same key as "Mahuan Dao"."""
    from pypinyin import lazy_pinyin   # only this generator needs it: pip install pypinyin
    out = set()
    for n in names:
        out.add(re.sub(r"[^a-z]", "", gz._fold(n)))
        if gz._is_cjk(n):
            out.add(re.sub(r"[^a-z]", "", "".join(lazy_pinyin(n))))
    return {k for k in out if len(k) > 5}


def linked(a_names, b_names, d) -> bool:
    """The same feature: close and sharing a name word, or within NAME_KM and sharing a whole name."""
    return (d <= MATCH_KM and bool(words(" ".join(a_names)) & words(" ".join(b_names)))) or \
           (d <= NAME_KM and bool(_keys(tuple(sorted(a_names))) & _keys(tuple(sorted(b_names)))))


def usable(name: str) -> bool:
    """A name worth matching in text: Latin or Chinese script, not a code, a URL or a bare number."""
    n = name.strip()
    if len(n) < 4 or "http" in n or re.fullmatch(r"[\d\W]+", n):
        return False
    if gz._is_cjk(n):
        return True
    return bool(re.fullmatch(r"[\w\s'’.\-()]+", n)) and not re.search(r"[Ѐ-ӿ؀-ۿ฀-๿가-힯぀-ヿ]", n)


def read_dump(path: Path):
    with zipfile.ZipFile(path) as z:
        member = next(n for n in z.namelist() if n.endswith(".txt") and not n.lower().startswith("readme"))
        with z.open(member) as f:
            for line in io.TextIOWrapper(f, encoding="utf-8"):
                p = line.rstrip("\n").split("\t")
                if len(p) < 9:
                    continue
                yield dict(zip(COLS, [p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8]]))


def collect(dumps: list[Path]) -> list[dict]:
    """GeoNames maritime features inside the sub-regions, one per place (the same reef in two countries'
    dumps, or listed twice, is merged when close and sharing a name word)."""
    found: list[dict] = []
    for d in dumps:
        for r in read_dump(d):
            if r["fcode"] not in CODES:
                continue
            lat, lon = float(r["lat"]), float(r["lon"])
            sr = gz.subregion_of(lat, lon)
            if sr is None:
                continue
            names = [n for n in [r["name"], r["asciiname"], *r["alternatenames"].split(",")] if n and usable(n)]
            if not names:
                continue
            item = {"id": r["geonameid"], "name": r["name"] if usable(r["name"]) else names[0], "names": set(names),
                    "lat": lat, "lon": lon, "sr": sr, "kind": CODES[r["fcode"]]}
            twin = next((f for f in found if linked(f["names"], names, km(f["lat"], f["lon"], lat, lon))), None)
            if twin:
                twin["names"] |= item["names"]
            else:
                found.append(item)
    return found


def build(dumps: list[Path], today: str) -> list[dict]:
    base = gz.load(gz.GAZETTEER, gz.GAZETTEER_EXTRA, geonames=Path("/nonexistent"))
    taken = {fid for fid in base}
    owner: dict[str, set[str]] = {}   # folded name -> the features that already carry it
    for fid, f in base.items():
        for n in f["names"]:
            owner.setdefault(gz._fold(n), set()).add(fid)

    def free(names, fid):
        """Names worth adding to `fid`: not generic, and not already another feature's (a shared name would
        make the matcher skip both, losing a placement the gazetteer has today)."""
        out = []
        for n in names:
            k = gz._fold(n)
            if not words(n) or owner.get(k, {fid}) - {fid}:
                continue
            out.append(n)
            owner.setdefault(k, set()).add(fid)
        return sorted(set(out))

    rows = []
    for g in collect(dumps):
        near = sorted(((km(g["lat"], g["lon"], f["lat"], f["lon"]), fid) for fid, f in base.items()
                       if f["kind"] != "island group"), key=lambda t: t[0])
        match = next((fid for d, fid in near[:40] if linked(base[fid]["names"], g["names"], d)), None)
        if match:
            known = {gz._fold(n) for n in base[match]["names"]}
            new = free([n for n in g["names"] if gz._fold(n) not in known], match)
            if new:
                rows.append({"feature_id": match, "aliases": "|".join(new), "retrieved": f"geonames {today}"})
            continue
        if g["kind"] == "island group":
            continue   # areas, not points: the map places features, and Wikidata already has the groups
        en = g["name"] if is_english(g["name"]) else next((n for n in sorted(g["names"]) if is_english(n)), "")
        if not en:
            continue   # only pinyin, Vietnamese or French names: the map would show no English name (ticket 32)
        fid = gz.slugify(en) or f"geonames-{g['id']}"
        if fid in taken:
            fid = f"{fid}-gn{g['id']}"
        g["names"] = set(free(g["names"], fid))
        if en not in g["names"]:
            continue   # its English name is another feature's: nothing it could place
        taken.add(fid)
        zh = next((n for n in sorted(g["names"]) if gz._is_cjk(n)), "")
        rows.append({"feature_id": fid, "name_en": en, "name_zh": zh,
                     "aliases": "|".join(sorted(n for n in g["names"] if n not in (en, zh))),
                     "lat": f"{g['lat']:.5f}", "lon": f"{g['lon']:.5f}", "subregion": str(g["sr"]), "kind": g["kind"],
                     "retrieved": f"geonames:{g['id']} {today}"})
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dumps", type=Path, nargs="+", required=True)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args(argv)
    rows = build(a.dumps, dt.date.today().isoformat())
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=gz.COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["feature_id"]):
            w.writerow({c: r.get(c, "") for c in gz.COLUMNS})
    added = sum(1 for r in rows if r.get("lat"))
    print(f"{a.out}: {added} new features, {len(rows) - added} with more names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
