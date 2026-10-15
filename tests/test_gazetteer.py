"""The gazetteer: every feature sits in the sub-region it claims; names in five languages resolve;
locating an event fills only what is blank; the validator holds coordinates and sub-region together."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipeline import gazetteer as g
from pipeline import validate

from tests.conftest import DATA_DIR, RAW_MAVD, RAW_XLSX


@pytest.fixture
def data_copy(tmp_path):
    import shutil
    d = tmp_path / "data"
    shutil.copytree(DATA_DIR, d, ignore=shutil.ignore_patterns("raw"))
    return d, RAW_XLSX, RAW_MAVD


def test_every_feature_lies_in_its_stated_subregion():
    feats = g.load()
    assert len(feats) > 250
    assert len({f["feature_id"] for f in feats.values()}) == len(feats)
    off = [fid for fid, f in feats.items() if f["subregion"] and g.subregion_of(f["lat"], f["lon"]) != f["subregion"]]
    assert off == []


def test_generated_file_has_provenance_and_the_extra_file_merges():
    with open(g.GAZETTEER, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and all(r["wikidata"].startswith("Q") and r["retrieved"] for r in rows)
    assert list(rows[0]) == g.COLUMNS
    feats = g.load()
    # a correction row keeps the generated coordinates and adds aliases
    assert feats["reed-tablemount"]["name_en"] == "Reed Bank" and "Recto Bank" in feats["reed-tablemount"]["names"]
    assert feats["reed-tablemount"]["wikidata"] == "Q7306628"
    # an added row
    assert feats["union-banks"]["subregion"] == 5


@pytest.mark.parametrize("point, expected", [
    ((7.52, 109.77), 9),     # Vanguard Bank
    ((9.55, 112.89), 8),     # Fiery Cross Reef
    ((11.05, 114.28), 5),    # Thitu
    ((15.18, 117.77), 4),    # Scarborough
    ((9.65, 115.85), 6),     # Second Thomas Shoal
    ((3.97, 112.35), 10),    # James Shoal
    ((20.70, 116.73), None), # Pratas, outside the ten
    ((39.9, 116.4), None),   # Beijing
])
def test_subregion_of_known_points(point, expected):
    assert g.subregion_of(*point) == expected


@pytest.mark.parametrize("text, feature", [
    ("Second Thomas Shoal (Ren'ai Jiao)", "second-thomas-shoal"),
    ("near Ayungin Shoal", "second-thomas-shoal"),
    ("Scarborough Shoal (Huangyan Dao)", "scarborough-shoal"),
    ("黄岩岛附近海域", "scarborough-shoal"),
    ("Bãi Tư Chính", "vanguard-bank"),
    ("Thitu Island and Sandy Cay (Zhongye Dao, Tiexian Jiao)", "pag-asa-island"),   # earliest name wins
    ("Hải Sâm (Antelope Reef) and Ba Ba Island, Paracels", "antelope-reef"),
    ("Whitsun Reef", "whitsum-reef"),
    ("Beting Patinggi Ali", "luconia-shoals"),
    ("Natuna waters", "natuna-islands"),
    ("waters off Luzon", None),
    ("Beijing", None),
    ("", None),
    ("Reedy area", None),   # no partial-word matches
])
def test_resolve_names_in_five_languages(text, feature):
    f = g.resolve(text)
    assert (f["feature_id"] if f else None) == feature


def test_locate_fills_blanks_only():
    e = g.locate({"location_name": "Mischief Reef", "lat": "", "lon": "", "subregion": "", "location_precision": ""})
    assert (e["lat"], e["lon"], e["subregion"], e["location_precision"]) == ("9.91667", "115.53333", "6", "feature")
    # stated values survive
    e = g.locate({"location_name": "Mischief Reef", "lat": "9.9", "lon": "115.5", "subregion": "", "location_precision": "point"})
    assert (e["lat"], e["subregion"], e["location_precision"]) == ("9.9", "6", "point")
    e = g.locate({"location_name": "Mischief Reef", "lat": "", "lon": "", "subregion": "7", "location_precision": "subregion"})
    assert (e["subregion"], e["location_precision"], e["lat"]) == ("7", "subregion", "9.91667")
    # an archipelago is an area: sub-region only, never a point; the Spratlys span several, so nothing
    e = g.locate({"location_name": "the Paracels", "lat": "", "lon": "", "subregion": "", "location_precision": "unknown"})
    assert (e["lat"], e["subregion"], e["location_precision"]) == ("", "2", "subregion")
    e = g.locate({"location_name": "the Spratly Islands", "lat": "", "lon": "", "subregion": "", "location_precision": "unknown"})
    assert (e["lat"], e["subregion"], e["location_precision"]) == ("", "", "unknown")
    # unknown name: untouched
    e = g.locate({"location_name": "somewhere", "lat": "", "lon": "", "subregion": "", "location_precision": "feature"})
    assert e["lat"] == "" and e["location_precision"] == "feature"


def test_validator_holds_coordinates_and_subregion_together(data_copy):
    """A located event whose stated sub-region disagrees with its coordinates fails; a point without
    coordinates fails; a feature without coordinates (name not in the gazetteer) passes."""
    d, xlsx, mavd = data_copy
    rows = list(csv.DictReader(open(d / "events.csv", newline="", encoding="utf-8")))
    e = next(r for r in rows if r["status"] == "accepted")
    e.update(lat="15.18", lon="117.77", subregion="6", location_precision="feature")
    _write(d / "events.csv", rows)
    errs = validate.validate(d, xlsx, mavd)
    assert any(err.startswith("LOCATION") and "lies in 4" in err for err in errs)
    e.update(lat="", lon="", subregion="", location_precision="point")
    _write(d / "events.csv", rows)
    assert any("is a point but lacks coordinates" in err for err in validate.validate(d, xlsx, mavd))
    e.update(location_precision="feature")
    _write(d / "events.csv", rows)
    assert not [err for err in validate.validate(d, xlsx, mavd) if err.startswith("LOCATION")]


def _write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
