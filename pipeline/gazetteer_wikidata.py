"""Build data/reference/gazetteer.csv from Wikidata: every named reef, island, shoal, bank, atoll,
cay or rock whose coordinates fall inside one of the ten MAVD sub-region polygons, with its English,
Chinese, Vietnamese, Filipino and Malay/Indonesian labels and aliases.

Run by hand when the gazetteer needs refreshing (it is committed; the site build and the validator
never call Wikidata). Hand additions and corrections go in data/reference/gazetteer_extra.csv, which
wins over this file on the same feature id.

  python -m pipeline.gazetteer_wikidata [--out data/reference/gazetteer.csv]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from pipeline.gazetteer import GAZETTEER, slugify, subregion_of

ENDPOINT = "https://query.wikidata.org/sparql"
UA = "SCS-Developments-Tracker/0.1 (research gazetteer; https://github.com/South-China-Sea-Developments/SCS-Developments-Tracker)"
# the box that encloses the ten polygons
BOX = ("Point(106.5 2.5)", "Point(120.0 21.5)")
# instance-of labels that are maritime features; everything else inside the polygons (ships, eclipses,
# battles, airports, lighthouses, villages, boundaries) is dropped
KEEP_TYPES = {"reef", "island", "shoal", "atoll", "ocean bank", "disputed territory", "island group", "archipelago",
              "skerry", "artificial island", "islet", "low-tide elevation", "guyot", "rock formation", "mudflat",
              "terra nullius", "stone", "char", "coral reef", "cay", "sandbank", "bank", "rock"}
# untyped items are kept when their name reads as a feature
NAME_LOOKS_LIKE_FEATURE = re.compile(r"(Reef|Shoal|Bank|Island|Islands|Rock|Cay|Atoll|Breakers|Patch|Tablemount|Sand|Shazhou|Jiao|Ansha|Tan|Dao|Yu)s?$"
                                     r"|[礁滩岛屿沙洲石堡]$|^(Đá|Bãi|Đảo|Cồn|Cụm|Núi|Rạch)\b", re.I)
KINDS = ["reef", "island", "shoal", "bank", "atoll", "cay", "rock", "island group", "other"]


def sparql(query: str) -> list[dict]:
    data = urllib.parse.urlencode({"query": query}).encode()
    req = urllib.request.Request(ENDPOINT, data=data, headers={"Accept": "text/csv", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r:
        return list(csv.DictReader(r.read().decode("utf-8").splitlines()))


Q_BOX = f"""SELECT ?item ?coord WHERE {{
  SERVICE wikibase:box {{
    ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "{BOX[0]}"^^geo:wktLiteral .
    bd:serviceParam wikibase:cornerNorthEast "{BOX[1]}"^^geo:wktLiteral .
  }}
}}"""

Q_LABELS = """SELECT ?item ?en ?zh ?zht ?vi ?tl ?ms ?id ?instLabel
  (GROUP_CONCAT(DISTINCT ?alias; separator="|") AS ?aliases) WHERE {
  VALUES ?item { %s }
  OPTIONAL { ?item wdt:P31 ?inst . }
  OPTIONAL { ?item rdfs:label ?en FILTER(LANG(?en)="en") }
  OPTIONAL { ?item rdfs:label ?zh FILTER(LANG(?zh)="zh") }
  OPTIONAL { ?item rdfs:label ?zht FILTER(LANG(?zht)="zh-tw") }
  OPTIONAL { ?item rdfs:label ?vi FILTER(LANG(?vi)="vi") }
  OPTIONAL { ?item rdfs:label ?tl FILTER(LANG(?tl)="tl") }
  OPTIONAL { ?item rdfs:label ?ms FILTER(LANG(?ms)="ms") }
  OPTIONAL { ?item rdfs:label ?id FILTER(LANG(?id)="id") }
  OPTIONAL { ?item skos:altLabel ?alias FILTER(LANG(?alias) IN ("en","zh","zh-tw","vi","tl","ms","id")) }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} GROUP BY ?item ?en ?zh ?zht ?vi ?tl ?ms ?id ?instLabel"""


def kind_of(insts: set[str], en: str) -> str:
    text = " ".join(insts) + " " + en
    for k, pat in (("reef", r"reef|skerry|low-tide|artificial island|atoll"), ("shoal", r"shoal|breakers|patch|mudflat"),
                   ("bank", r"bank|guyot|tablemount"), ("cay", r"\bcay\b|sand\b|shazhou|sandbank"),
                   ("rock", r"\brock|stone|\bchar\b"), ("island group", r"island group|archipelago"),
                   ("island", r"island|islet|disputed territory|terra nullius")):
        if re.search(pat, text, re.I):
            return "atoll" if k == "reef" and "atoll" in insts and "reef" not in insts else k
    return "other"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=GAZETTEER)
    a = p.parse_args(argv)
    print("querying the bounding box ...", file=sys.stderr)
    inside: dict[str, tuple[float, float, int]] = {}
    for r in sparql(Q_BOX):
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", r["coord"])
        if not m:
            continue
        lon, lat = float(m.group(1)), float(m.group(2))
        sr = subregion_of(lat, lon)
        if sr and r["item"] not in inside:
            inside[r["item"]] = (lat, lon, sr)
    print(f"{len(inside)} items inside the polygons; fetching labels ...", file=sys.stderr)
    qids = ["wd:" + i.rsplit("/", 1)[-1] for i in inside]
    by: dict[str, dict] = {}
    for i in range(0, len(qids), 150):
        for r in sparql(Q_LABELS % " ".join(qids[i:i + 150])):
            d = by.setdefault(r["item"], dict(r, insts=set()))
            d["insts"].add(r["instLabel"])
    rows = []
    for item, d in by.items():
        insts = {i for i in d["insts"] if i}
        en = d["en"] or ""
        if insts and not insts & KEEP_TYPES:
            continue
        if not insts and not NAME_LOOKS_LIKE_FEATURE.search(en or d["zh"] or d["vi"] or ""):
            continue
        name = en or d["zht"] or d["zh"] or d["vi"] or ""
        if not name:
            continue
        lat, lon, sr = inside[item]
        aliases = sorted({x.strip() for x in d["aliases"].split("|") if x.strip()} | {d["zht"]} - {"", name, d["zh"], d["vi"], d["tl"], d["ms"], d["id"]})
        rows.append({"feature_id": slugify(name), "name_en": en, "name_zh": d["zh"] or d["zht"], "name_vi": d["vi"], "name_fil": d["tl"],
                     "name_ms": d["ms"] or d["id"], "aliases": "|".join(aliases), "lat": f"{lat:.5f}", "lon": f"{lon:.5f}",
                     "subregion": sr, "kind": kind_of(insts, en), "wikidata": item.rsplit("/", 1)[-1],
                     "retrieved": dt.date.today().isoformat()})
    # duplicate ids (same English name twice, e.g. "North Reef" in two sub-regions) get the sub-region appended
    seen: dict[str, int] = {}
    for r in rows:
        seen[r["feature_id"]] = seen.get(r["feature_id"], 0) + 1
    for r in rows:
        if seen[r["feature_id"]] > 1:
            r["feature_id"] = f"{r['feature_id']}-{r['subregion']}"
    rows.sort(key=lambda r: (r["subregion"], r["feature_id"]))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} features -> {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
