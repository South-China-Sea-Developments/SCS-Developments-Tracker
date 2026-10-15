"""Seam 1: the validator passes on good data and goes red on each rule."""
import csv
from pathlib import Path

import pytest

from pipeline.validate import main, validate
from tests.conftest import DATA_DIR, RAW_MAVD, RAW_XLSX


def write_dir(tmp_path, tables):
    from pipeline.schema import TABLES

    d = tmp_path / "data"
    d.mkdir()
    for name in TABLES:
        with open(d / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=TABLES[name])
            w.writeheader()
            w.writerows(tables.get(name, []))  # corrections: always an empty table here
    return d


@pytest.fixture
def good(tmp_path, loaded):
    return write_dir(tmp_path, loaded)


def edit(d: Path, table: str, fn):
    path = d / f"{table}.csv"
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows, fields = list(r), r.fieldnames
    rows = fn(rows)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def codes(errors):
    return {e.split(":")[0] for e in errors}


def test_good_data_passes(good):
    assert validate(good, RAW_XLSX, RAW_MAVD) == []


def test_committed_data_passes():
    if not (DATA_DIR / "moves.csv").exists():
        pytest.skip("canonical files not generated yet")
    assert validate(DATA_DIR, RAW_XLSX, RAW_MAVD) == []


def test_cli_exit_codes(good, capsys):
    assert main(["--data", str(good), "--xlsx", str(RAW_XLSX), "--mavd", str(RAW_MAVD)]) == 0
    assert "OK" in capsys.readouterr().out
    edit(good, "moves", lambda rows: rows[1:])
    assert main(["--data", str(good), "--xlsx", str(RAW_XLSX), "--mavd", str(RAW_MAVD)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_extra_project_move_in_mats_scope_is_caught(good):
    def fn(rows):
        extra = dict(rows[0])
        extra.update(move_id="CN201099", year="2010", instance_no="99", coded_by="project", coder="test",
                     data_version="2.0.0-dev", status="accepted")
        rows.append(extra)
        return rows
    edit(good, "moves", fn)
    errs = validate(good, RAW_XLSX, RAW_MAVD)
    assert any(e.startswith("COMPARABILITY: CN 2010") for e in errs)


def test_pending_mavd_move_accepted_is_caught(good):
    def fn(rows):
        for r in rows:
            if r["move_id"] == "VN197304":
                r["status"] = "accepted"
        return rows
    edit(good, "moves", fn)
    errs = validate(good, RAW_XLSX, RAW_MAVD)
    assert any(e.startswith("COMPARABILITY: VN 1973") for e in errs)


def test_mavd_extra_column_edit_without_correction_is_caught(good):
    def fn(rows):
        for r in rows:
            if r["move_id"] == "CN201105":
                r["other_possible_cases"] = "edited"
        return rows
    edit(good, "moves", fn)
    assert any("other_possible_cases" in e for e in validate(good, RAW_XLSX, RAW_MAVD))


def test_malformed_correction_row_is_caught(good):
    with open(good / "corrections.csv", "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["ZZ000000", "nonsense", "x", "2026-10-15", "test", "typo"])
    assert "CODE" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_schema_violation(good):
    path = good / "moves.csv"
    text = path.read_text(encoding="utf-8").replace("move_id,", "id,", 1)
    path.write_text(text, encoding="utf-8")
    assert "SCHEMA" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_unknown_code(good):
    def fn(rows):
        rows[0]["claimant"] = "XX"
        return rows
    edit(good, "moves", fn)
    assert "CODE" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_move_without_type_flag(good):
    def fn(rows):
        for k in ("declarative", "demonstrative", "coercive", "force"):
            rows[0][k] = "0"
        return rows
    edit(good, "moves", fn)
    assert "NO_TYPE" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_event_with_missing_move(good):
    def fn(rows):
        rows[0]["move_id"] = "ZZ000000"
        return rows
    edit(good, "events", fn)
    assert "EVENT_MOVE" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_candidate_event_may_have_no_move(good):
    def fn(rows):
        rows[0]["move_id"] = ""
        rows[0]["status"] = "candidate"
        return rows
    edit(good, "events", fn)
    assert "EVENT_MOVE" not in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_source_with_missing_event(good):
    def fn(rows):
        rows[0]["event_id"] = "ZZ000000-E99"
        return rows
    edit(good, "sources", fn)
    assert "SOURCE_EVENT" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_accepted_event_without_source(good):
    def fn(rows):
        return rows[1:]
    edit(good, "sources", fn)
    assert "EVENT_NO_SOURCE" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_duplicate_id(good):
    def fn(rows):
        rows.append(dict(rows[0]))
        return rows
    edit(good, "moves", fn)
    assert "DUPLICATE" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_comparability_count_drift(good):
    def fn(rows):
        return [r for r in rows if r["move_id"] != "CN201105"]
    edit(good, "moves", fn)
    assert "COMPARABILITY" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_comparability_flag_drift(good):
    def fn(rows):
        for r in rows:
            if r["move_id"] == "CN201105":
                r["coercive"] = "0" if r["coercive"] == "1" else "1"
        return rows
    edit(good, "moves", fn)
    assert "COMPARABILITY" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_comparability_description_drift_without_correction(good):
    def fn(rows):
        for r in rows:
            if r["move_id"] == "CN201105":
                r["description"] = r["description"] + " (edited)"
        return rows
    edit(good, "moves", fn)
    assert "COMPARABILITY" in codes(validate(good, RAW_XLSX, RAW_MAVD))


def test_documented_correction_is_allowed(good):
    new_text = None

    def fn(rows):
        nonlocal new_text
        for r in rows:
            if r["move_id"] == "CN201105":
                new_text = r["description"] + " (corrected)"
                r["description"] = new_text
        return rows
    edit(good, "moves", fn)
    with open(good / "corrections.csv", "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["CN201105", "description", new_text, "2026-10-15", "test", "test correction"])
    assert validate(good, RAW_XLSX, RAW_MAVD) == []
