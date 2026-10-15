"""Seam 1: the canonical tables built from MATS 1.02 + MAVD reproduce the original exactly."""
import csv
from collections import Counter

import pytest

from tests.conftest import RAW_MAVD

from pipeline import schema

SUBREGION_COLS = schema.SUBREGION_FLAGS
XLSX_SUBREGION_COLS = [schema.MATS_XLSX_COLUMNS[c] for c in SUBREGION_COLS]


def accepted_chubb(loaded):
    return [m for m in loaded["moves"] if m["coded_by"] == "chubb" and m["status"] == "accepted"]


def test_claimants(loaded):
    assert [c["code"] for c in loaded["claimants"]] == ["CN", "VN", "PH", "MY", "ID", "TW"]


def test_357_accepted_moves_with_published_counts(loaded):
    moves = accepted_chubb(loaded)
    assert len(moves) == 357
    assert Counter(m["claimant"] for m in moves) == {"CN": 144, "VN": 111, "PH": 102}
    assert all(m["data_version"] == "1.02" for m in moves)
    totals = {t: sum(int(m[t]) for m in moves) for t in ("declarative", "demonstrative", "coercive", "force")}
    assert totals == {"declarative": 90, "demonstrative": 175, "coercive": 75, "force": 17}


def test_every_move_matches_its_xlsx_row(loaded, raw_xlsx_rows):
    by_id = {m["move_id"]: m for m in accepted_chubb(loaded)}
    assert set(by_id) == {r["AltCaseNo"] for r in raw_xlsx_rows}
    for r in raw_xlsx_rows:
        m = by_id[r["AltCaseNo"]]
        assert m["claimant"] == r["CountryCode"]
        assert int(m["year"]) == r["Year"]
        assert m["description"] == r["Case description and sources"].strip()
        assert m["dyads"] == r["Dyads"]
        assert int(m["ongoing_through"]) == r["Ongoing through"]
        for ours, theirs in zip(SUBREGION_COLS, XLSX_SUBREGION_COLS):
            assert int(m[ours]) == r[theirs], (r["AltCaseNo"], ours)


def test_packed_codes_reproduce_xlsx(loaded, raw_xlsx_rows):
    from pipeline.schema import packed_domains, packed_issues, packed_locations

    by_id = {m["move_id"]: m for m in accepted_chubb(loaded)}
    for r in raw_xlsx_rows:
        m = by_id[r["AltCaseNo"]]
        if r["AltCaseNo"] == "PH197701":
            # xlsx internal inconsistency: Domains=3 but Physical flag=0; flags win, logged for the author
            assert packed_domains(m) == 0 and int(r["Domains"]) == 3
        else:
            assert packed_domains(m) == int(r["Domains"]), r["AltCaseNo"]
        assert packed_issues(m) == int(r["Issues"]), r["AltCaseNo"]
        assert packed_locations(m) == int(r["Locations"]), r["AltCaseNo"]


def test_vn197304_is_pending_and_excluded_from_counts(loaded):
    pending = [m for m in loaded["moves"] if m["status"] == "pending"]
    assert [m["move_id"] for m in pending] == ["VN197304"]
    m = pending[0]
    assert m["coded_by"] == "chubb" and m["data_version"] == "mavd-2023"
    assert m["declarative"] == "1" and m["domestic"] == "1" and m["loc02_paracels"] == "1"
    assert len(loaded["moves"]) == 358


def test_mavd_extra_columns_imported(loaded):
    moves = loaded["moves"]
    assert sum(1 for m in moves if m["diminished_notes"]) == 57
    assert sum(1 for m in moves if m["other_possible_cases"]) == 77


def test_seed_events_one_per_date_token_with_sources(loaded):
    with open(RAW_MAVD, encoding="utf-8") as f:
        dates = {r["AltCaseNo"]: r["Dates"] for r in csv.DictReader(f) if r["Dates"]}
    expected_tokens = sum(len(v.split(";")) for v in dates.values())
    events = loaded["events"]
    assert len(events) == expected_tokens
    assert {e["move_id"] for e in events} == set(dates)
    assert {e["status"] for e in events if e["move_id"] != "VN197304"} == {"accepted"}
    assert [e["status"] for e in events if e["move_id"] == "VN197304"] == ["candidate"]  # pending move
    assert all(e["date_precision"] in ("day", "month", "year") for e in events)
    assert all(e["reviewer"] == "Andrew Chubb" and e["review_date"] for e in events)
    assert all(e["location_precision"] == "unknown" and e["subregion"] == "" for e in events)
    by_move = Counter(e["move_id"] for e in events)
    assert by_move["VN197301"] == 5
    # dated precisely
    e = next(e for e in events if e["event_id"] == "VN197401-E01")
    assert (e["date_start"], e["date_end"], e["date_precision"]) == ("1974-01-18", "1974-01-18", "day")
    e = next(e for e in events if e["event_id"] == "VN197101-E01")
    assert (e["date_start"], e["date_end"], e["date_precision"]) == ("1971-05-01", "1971-05-31", "month")
    e = next(e for e in events if e["event_id"] == "VN197404-E01")
    assert (e["date_start"], e["date_end"], e["date_precision"]) == ("1974-01-01", "1974-12-31", "year")
    e = next(e for e in events if e["event_id"] == "VN197508-E01")
    assert e["date_precision"] == "month" and "approximate" in e["summary"].lower()
    # one source per seed event, pointing at the MATS description
    sources = loaded["sources"]
    assert Counter(s["event_id"] for s in sources) == Counter(e["event_id"] for e in events)
    assert all(s["excerpt"] for s in sources)


def test_seed_event_dates_outside_move_years_are_flagged(loaded):
    anomalies = {(a["move_id"], a["event_id"]) for a in loaded["anomalies"]}
    assert anomalies == {("VN197601", "VN197601-E01"), ("VN199303", "VN199303-E02"), ("VN201302", "VN201302-E01")}
    e = next(e for e in loaded["events"] if e["event_id"] == "VN201302-E01")
    assert "outside the move's year" in e["review_note"].lower()


def test_flag_values_other_than_0_1_are_rejected():
    from pipeline.load_mats import _flag

    assert _flag(None) == "0" and _flag(1) == "1" and _flag("0") == "0"
    with pytest.raises(ValueError):
        _flag(2, "test")
    with pytest.raises(ValueError):
        _flag(0.5, "test")


def test_description_and_flag_differences_logged(loaded):
    log = loaded["differences"]
    assert sum(1 for d in log if d["kind"] == "description") == 75
    flag_diffs = {(d["move_id"], d["field"]) for d in log if d["kind"] == "flag"}
    assert flag_diffs == {
        ("VN197302", "loc03_central_west"), ("VN197302", "loc04_central_east"),
        ("VN197306", "military"), ("VN197306", "energy"), ("VN197306", "fisheries"), ("VN197306", "politics"),
        ("VN197404", "loc03_central_west"), ("VN197404", "loc04_central_east"),
        ("PH197701", "physical"),
        ("VN199801", "energy"), ("VN199801", "fisheries"),
        ("PH199902", "loc06_spratly_ne"), ("PH199902", "loc07_spratly_se"),
        ("VN200704", "loc04_central_east"), ("VN200803", "loc04_central_east"),
        ("VN200804", "loc04_central_east"), ("VN200805", "loc04_central_east"),
        ("VN201102", "loc04_central_east"),
        ("PH201404", "physical"),
    }
    # xlsx-internal inconsistency between packed code and flags is logged too
    assert [(d["move_id"], d["field"]) for d in log if d["kind"] == "xlsx-internal"] == [("PH197701", "Domains")]


def test_loader_is_deterministic(loaded):
    from pipeline.load_mats import load_tables
    from tests.conftest import RAW_XLSX

    again = load_tables(RAW_XLSX, RAW_MAVD)
    assert again == loaded
