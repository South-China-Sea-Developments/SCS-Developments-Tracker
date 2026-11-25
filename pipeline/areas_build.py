"""Build data/reference/areas.csv: named sea areas that are not reefs or islands, with the share of each
of the ten sub-regions they cover (ticket 33). It lets a candidate whose place is "off Sabah", "the
Bruneian EEZ" or "Block K" come to review with its sub-regions suggested.

Three kinds of area, all reduced to sub-region shares (no geometry is kept in the repository):
- coast: the sea within about 150 km of a coastal province (Natural Earth admin-1, public domain);
- eez: an exclusive economic zone (Marine Regions EEZ v12, CC BY 4.0, doi:10.14284/632);
- block: an oil or gas block or field, from sourced points (data/reference/area_points.csv).
A share is the fraction of a 0.05-degree grid over the area that falls in each sub-region.

Run by hand when a source changes; the build and the validator only read the CSV:

  python -m pipeline.areas_build --admin1 ne_10m_admin_1_states_provinces.geojson --eez eez.json

The two inputs: github.com/nvkelso/natural-earth-vector (geojson/), and the Marine Regions WFS
(typeName MarineRegions:eez, outputFormat application/json, bbox 103,0,123,25).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from shapely import contains_xy, prepare
from shapely.geometry import MultiPoint, shape
from shapely.ops import unary_union

from pipeline import gazetteer as gz

REFERENCE = gz.GAZETTEER.parent
OUT = REFERENCE / "areas.csv"
POINTS = REFERENCE / "area_points.csv"
COLUMNS = ["area_id", "name", "aliases", "kind", "shares", "source"]
STEP = 0.05
BANDS = (1.35, 2.0, 2.7)   # degrees of sea around a coastal province (~150, 220, 300 km), widened until it meets a sub-region
MIN_CELLS = 40       # an area with fewer grid cells in the sub-regions is left out

# coastal provinces on the sea; the aliases are how sources write them
COASTS = {
    ("Malaysia", "Sabah"): [], ("Malaysia", "Sarawak"): [], ("Malaysia", "Labuan"): [],
    ("Malaysia", "Terengganu"): [], ("Malaysia", "Kelantan"): [], ("Malaysia", "Pahang"): [],
    ("Philippines", "Palawan"): [], ("Philippines", "Zambales"): [], ("Philippines", "Pangasinan"): [],
    ("Philippines", "Bataan"): [], ("Philippines", "Ilocos Norte"): [], ("Philippines", "Ilocos Sur"): [],
    ("Philippines", "La Union"): [], ("Philippines", "Mindoro Occidental"): ["Occidental Mindoro"],
    ("Philippines", "Batangas"): [],
    ("China", "Hainan"): [], ("China", "Guangdong"): [], ("China", "Guangxi"): [],
    ("Taiwan", "Kaohsiung"): [], ("Taiwan", "Pingtung"): ["Pingtung County"],
    ("Indonesia", "Kepulauan Riau"): ["Riau Islands", "Natuna Islands", "Natuna"],
    ("Indonesia", "Kalimantan Barat"): ["West Kalimantan"],
}
VN_COASTAL = ["Quảng Ninh", "Hải Phòng", "Thái Bình", "Nam Định", "Ninh Bình", "Thanh Hóa", "Nghệ An", "Ha Tinh",
              "Quảng Bình", "Quảng Trị", "Thừa Thiên - Huế", "Đà Nẵng", "Quàng Nam", "Quảng Ngãi", "Bình Định",
              "Phú Yên", "Khánh Hòa", "Ninh Thuận", "Bình Thuận", "Bà Rịa - Vũng Tàu", "Tiền Giang", "Bến Tre",
              "Trà Vinh", "Sóc Trăng", "Bạc Liêu", "Cà Mau", "Kiên Giang"]
VN_FIX = {"Quàng Nam": "Quảng Nam", "Ha Tinh": "Hà Tĩnh", "Thừa Thiên - Huế": "Thừa Thiên Huế", "Bà Rịa - Vũng Tàu": "Bà Rịa–Vũng Tàu"}
EEZ_NAMES = {   # Marine Regions geoname -> (id, English name, aliases)
    "Philippine Exclusive Economic Zone": ("eez-ph", "Philippine EEZ", ["Philippines' EEZ", "Philippine exclusive economic zone", "West Philippine Sea"]),
    "Vietnamese Exclusive Economic Zone": ("eez-vn", "Vietnamese EEZ", ["Vietnam's EEZ", "Vietnamese exclusive economic zone"]),
    "Bruneian Exclusive Economic Zone": ("eez-bn", "Bruneian EEZ", ["Brunei's EEZ", "Brunei EEZ", "Bruneian waters", "Brunei's continental shelf", "Bruneian continental shelf",
                                                                   "Bruneian Exclusive Economic Zone", "Brunei's exclusive economic zone", "Bruneian fishery limits", "Brunei Darussalam fishery limits"]),
    "Malaysian Exclusive Economic Zone": ("eez-my", "Malaysian EEZ", ["Malaysia's EEZ", "Malaysian waters", "Malaysia's continental shelf", "Malaysian continental shelf"]),
    "Indonesian Exclusive Economic Zone": ("eez-id", "Indonesian EEZ", ["Indonesia's EEZ", "Indonesian waters"]),
    "Chinese Exclusive Economic Zone": ("eez-cn", "Chinese EEZ", ["China's EEZ"]),
}


# seas and basins named after a sub-region or lying wholly in one (the MAVD sub-region names)
SEAS = [("sea-tonkin", "Gulf of Tonkin", ["Tonkin Gulf", "Beibu Gulf", "Gulf of Beibu", "Vịnh Bắc Bộ"], {1: 1.0}),
        ("sea-nam-con-son", "Nam Con Son Basin", ["Nam Con Son basin", "Nam Côn Sơn"], {9: 1.0}),
        ("sea-natuna", "Natuna Sea", ["North Natuna Sea", "Laut Natuna Utara"], {10: 1.0})]


def grid(geom):
    """Grid cells of `geom` that lie in a sub-region, as a Counter of sub-region numbers."""
    minx, miny, maxx, maxy = geom.bounds
    xs, ys = np.meshgrid(np.arange(minx, maxx, STEP) + STEP / 2, np.arange(miny, maxy, STEP) + STEP / 2)
    xs, ys = xs.ravel(), ys.ravel()
    prepare(geom)
    inside = contains_xy(geom, xs, ys)
    counts: dict[int, int] = {}
    for n, poly in SUBREGIONS:
        k = int(contains_xy(poly, xs[inside], ys[inside]).sum())
        if k:
            counts[n] = k
    return counts


def shares(counts) -> str:
    total = sum(counts.values())
    return "|".join(f"{n}:{c / total:.2f}" for n, c in sorted(counts.items(), key=lambda t: -t[1]) if c / total >= 0.005)


def main(argv=None) -> int:
    global SUBREGIONS
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--admin1", type=Path, required=True)
    p.add_argument("--eez", type=Path, required=True)
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args(argv)
    sr = json.loads(gz.SUBREGIONS.read_text(encoding="utf-8"))
    SUBREGIONS = [(int(f["properties"]["LocationNo"]), shape(f["geometry"])) for f in sr["features"]]
    for _, poly in SUBREGIONS:
        prepare(poly)
    rows = []
    admin = json.loads(a.admin1.read_text(encoding="utf-8"))["features"]
    by_name = {}
    for f in admin:
        by_name.setdefault((f["properties"]["admin"], f["properties"]["name"]), []).append(shape(f["geometry"]))
    coasts = dict(COASTS)
    for v in VN_COASTAL:
        coasts[("Vietnam", v)] = []
    coasts[("Brunei", "*")] = ["Brunei"]
    land = unary_union([shape(f["geometry"]) for f in admin if f["properties"]["admin"] in
                        {"China", "Vietnam", "Philippines", "Malaysia", "Brunei", "Indonesia", "Taiwan", "Cambodia", "Thailand"}])
    for (country, prov), aliases in coasts.items():
        geoms = [g for (c, n), gs in by_name.items() for g in gs if c == country and (prov == "*" or n == prov)]
        if not geoms:
            print("missing", country, prov, file=sys.stderr)
            continue
        geom = unary_union(geoms)
        for width in BANDS:   # the polygons stop short of some coasts (off Vung Tau, the nearest is 9)
            counts = grid(geom.buffer(width).difference(land))
            if sum(counts.values()) >= MIN_CELLS:
                break
        else:
            continue
        name = VN_FIX.get(prov, prov) if prov != "*" else "Brunei"
        folded = gz._fold(name)
        al = sorted({*aliases, *( [folded.title()] if folded != name.casefold() else [])} - {name})
        rows.append({"area_id": "coast-" + gz.slugify(gz._fold(f"{country} {name}")), "name": name, "aliases": "|".join(al), "kind": "coast",
                     "shares": shares(counts), "source": f"Natural Earth admin-1 (public domain), sea within ~{round(width * 111, -1):.0f} km"})
    for f in json.loads(a.eez.read_text(encoding="utf-8"))["features"]:
        hit = EEZ_NAMES.get(f["properties"].get("geoname"))
        if not hit:
            continue
        counts = grid(shape(f["geometry"]))
        rows.append({"area_id": hit[0], "name": hit[1], "aliases": "|".join(hit[2]), "kind": "eez", "shares": shares(counts),
                     "source": "Marine Regions EEZ v12 (CC BY 4.0, doi:10.14284/632)"})
    for aid, name, aliases, sh in SEAS:
        rows.append({"area_id": aid, "name": name, "aliases": "|".join(aliases), "kind": "sea",
                     "shares": "|".join(f"{n}:{v:.2f}" for n, v in sh.items()), "source": "MAVD sub-region names"})
    for r in csv.DictReader(open(POINTS, encoding="utf-8")):
        pts = [tuple(map(float, x.split())) for x in r["points"].split(";")]
        counts = {}
        for lat, lon in pts:
            n = gz.subregion_of(lat, lon)
            if n:
                counts[n] = counts.get(n, 0) + 1
        if counts:
            rows.append({"area_id": r["area_id"], "name": r["name"], "aliases": r["aliases"], "kind": "block",
                         "shares": shares(counts), "source": r["source"]})
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["area_id"]))
    print(f"{a.out}: {len(rows)} areas")
    return 0


SUBREGIONS: list = []

if __name__ == "__main__":
    sys.exit(main())
