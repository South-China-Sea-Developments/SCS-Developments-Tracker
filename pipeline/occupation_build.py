"""Build data/reference/occupation.csv: who holds each occupied feature (ticket 36), for the map's
occupation layer and the feature pages.

Source: the occupation table of English Wikipedia's "List of maritime features in the Spratly Islands"
(its "Int'l Name || Co-ords || Sub-group || Occupant/s || Since || Notes" table), matched to the
gazetteer by name and position; plus two rows the table does not cover, written here with their
sources: the Paracel Islands (all held by China since January 1974) and Scarborough Shoal (controlled
by China since the 2012 standoff, without a structure). Louisa Reef is left out: Wikipedia gives it to
Brunei and says in the same article that Malaysia keeps a lighthouse there.

Run by hand when the source changes:

  python -m pipeline.occupation_build --wiki spratly.wiki    # the article's wikitext (action=raw)
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from pipeline import gazetteer as gz

OUT = gz.GAZETTEER.parent / "occupation.csv"
COLUMNS = ["feature_id", "holder", "since", "note", "source"]
FLAG = {"ROC": "TW", "PRC": "CN", "VNM": "VN", "VIE": "VN", "PHI": "PH", "PHL": "PH", "MAS": "MY", "MYS": "MY", "BRU": "BN"}
WIKI = "Wikipedia, List of maritime features in the Spratly Islands (occupation table), retrieved {date}"
LEFT_OUT = {"louisa-reef"}   # disputed control, see the docstring
EXTRA = [
    {"feature_id": "paracel-islands", "holder": "CN", "since": "1974",
     "note": "All the Paracels, since China took the Crescent Group from South Vietnam in January 1974",
     "source": "Wikipedia, Paracel Islands, retrieved {date}"},
    {"feature_id": "scarborough-shoal", "holder": "CN", "since": "2012",
     "note": "Controlled by the China Coast Guard since the 2012 standoff; no structure",
     "source": "Wikipedia, Scarborough Shoal, retrieved {date}"},
]


def _coord(cell: str) -> tuple[float, float]:
    p = [x for x in re.search(r"coord\|([^}]*)\}", cell).group(1).split("|") if "=" not in x]
    i, j = p.index("N"), p.index("E")
    return (round(sum(float(x) / 60 ** k for k, x in enumerate(p[:i])), 4),
            round(sum(float(x) / 60 ** k for k, x in enumerate(p[i + 1:j])), 4))


def _text(cell: str) -> str:
    cell = re.sub(r"<ref.*?(</ref>|/>)", "", cell)
    cell = re.sub(r"\{\{ill\|([^|}]*)[^}]*\}\}", r"\1", cell)
    cell = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", cell)
    return re.sub(r"\{\{[^}]*\}\}|'''|''|<[^>]+>", "", cell).strip()


def rows_from_wiki(wiki: str, date: str) -> list[dict]:
    start = wiki.index("Int'l Name            || Co-ords")
    table = wiki[start:wiki.index("|}", start)]
    feats = gz.load()
    out = []
    for r in table.split("|-")[1:]:
        c = [x.strip() for x in re.sub(r"\s+", " ", r).strip(" |").split("||")]
        if len(c) < 5:
            continue
        holders = [FLAG[f] for f in re.findall(r"flagu\|([A-Z]{3})", c[3]) if f in FLAG]
        if not holders:
            continue
        name = _text(c[0]).split("/")[0].strip()
        lat, lon = _coord(c[1])
        fid, dist = min(((k, gz_km(lat, lon, f["lat"], f["lon"])) for k, f in feats.items() if f["kind"] != "island group"),
                        key=lambda t: t[1])
        named = gz.resolve(name)
        exact = next((k for k, f in feats.items() if f["name_en"] == name and f["kind"] != "island group"), None)
        if exact:   # the article's coordinates are sometimes wrong (Spratly Island's longitude); its names are not
            fid = exact
        elif named and named["kind"] != "island group" and gz_km(lat, lon, named["lat"], named["lon"]) < 30:
            fid = named["feature_id"]
        elif dist > 3:
            print(f"no gazetteer feature for {name} ({lat}, {lon})", file=sys.stderr)
            continue
        if fid in LEFT_OUT:
            continue
        since = re.sub(r"[^\d/]", "", _text(c[4]))[:4]
        out.append({"feature_id": fid, "holder": " ".join(holders), "since": since,
                    "note": _text(c[5]) if len(c) > 5 else "", "source": WIKI.format(date=date)})
    return out


def gz_km(a_lat, a_lon, b_lat, b_lon) -> float:
    from pipeline.gazetteer_geonames import km
    return km(a_lat, a_lon, b_lat, b_lon)


def main(argv=None) -> int:
    import datetime as dt
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--wiki", type=Path, required=True)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--date", default=dt.date.today().isoformat())
    a = p.parse_args(argv)
    rows = rows_from_wiki(a.wiki.read_text(encoding="utf-8"), a.date) + [{k: v.format(date=a.date) for k, v in r.items()} for r in EXTRA]
    seen, uniq = set(), []
    for r in rows:
        if r["feature_id"] not in seen:
            seen.add(r["feature_id"])
            uniq.append(r)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(uniq, key=lambda r: (r["holder"], r["feature_id"])))
    print(f"{a.out}: {len(uniq)} held features")
    return 0


if __name__ == "__main__":
    sys.exit(main())
