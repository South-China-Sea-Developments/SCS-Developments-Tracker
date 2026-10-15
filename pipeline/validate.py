"""Validate the canonical files. Exit 1 with one line per error; exit 0 when clean.

Rules (docs/spec.md, "Validator"):
  SCHEMA          columns of each table are exactly the schema's
  CODE            codes within allowed sets (claimant, status, precision, flags 0/1, dyad letters)
  NO_TYPE         a move must have at least one Type flag
  EVENT_MOVE      a non-candidate event must point at an existing move
  SOURCE_EVENT    a source must point at an existing event
  EVENT_NO_SOURCE an accepted event must have at least one source
  DUPLICATE       identifiers are unique
  COMPARABILITY   CN/VN/PH 1970-2015 moves with coded_by=chubb equal MATS 1.02 (counts per
                  claimant-year, Type totals, and every field of every row) apart from
                  corrections documented in corrections.csv

The comparability check reads the raw xlsx with its own small reader, independent of the loader.

Usage: python -m pipeline.validate [--data data] [--xlsx data/raw/mats-1.02/MATS_1-02_all_cases.xlsx]
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from pipeline import schema

XLSX_FIELDS = {  # canonical column -> xlsx column
    "claimant": "CountryCode", "year": "Year", "dyads": "Dyads",
    "description": "Case description and sources", "ongoing_through": "Ongoing through",
    "ongoing_through_notes": "Ongoing through notes", "org_case_no": "OrgCaseNo",
    "declarative": "Declarative", "demonstrative": "Demonstrative", "coercive": "Coercive", "force": "Force",
    "domestic": "Domestic", "diplomatic": "Diplomatic", "physical": "Physical",
    "military": "Military", "administrative": "Administrative", "energy": "Energy",
    "fisheries": "Fisheries", "politics": "Politics",
    "loc01_tonkin": "Tonkin", "loc02_paracels": "Paracels", "loc03_central_west": "CentralWest",
    "loc04_central_east": "CentralEast", "loc05_spratly_nw": "SpratlyNW", "loc06_spratly_ne": "SpratlyNE",
    "loc07_spratly_se": "SpratlySE", "loc08_spratly_sw": "SpratlySW", "loc09_nam_con_son": "NamConSon",
    "loc10_far_south": "FarSouth",
}


def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def _norm(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def read_mats_xlsx(path: Path) -> dict[str, dict]:
    """Rows of MATS 1.02 keyed by AltCaseNo, values normalised to the canonical string form."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True)
    rows = list(wb["MATS 1.02 cases"].iter_rows(values_only=True))
    header = rows[0]
    out = {}
    for r in rows[1:]:
        if not r[2]:
            continue
        d = dict(zip(header, r))
        rec = {}
        for col, xcol in XLSX_FIELDS.items():
            v = d[xcol]
            rec[col] = ("1" if int(v) else "0") if col in schema.FLAG_COLUMNS else _norm(v)
        out[_norm(d["AltCaseNo"])] = rec
    return out


def validate(data_dir: Path, xlsx_path: Path | None) -> list[str]:
    data_dir = Path(data_dir)
    errors: list[str] = []
    tables: dict[str, list[dict]] = {}

    for name, columns in schema.TABLES.items():
        path = data_dir / f"{name}.csv"
        if not path.exists():
            if name == "corrections":
                tables[name] = []
                continue
            errors.append(f"SCHEMA: missing table {name}.csv")
            continue
        fields, rows = _read_csv(path)
        if fields != columns:
            errors.append(f"SCHEMA: {name}.csv columns are {fields}, expected {columns}")
        tables[name] = rows
    if any(e.startswith("SCHEMA") for e in errors):
        return errors

    for name, idcol in schema.ID_COLUMN.items():
        dup = [k for k, n in Counter(r[idcol] for r in tables[name]).items() if n > 1]
        for k in dup:
            errors.append(f"DUPLICATE: {name}.{idcol} {k}")

    claimants = {r["code"] for r in tables["claimants"]}
    for c in claimants - set(schema.CLAIMANT_CODES):
        errors.append(f"CODE: claimants.code {c} not in {schema.CLAIMANT_CODES}")

    moves = tables["moves"]
    for m in moves:
        mid = m["move_id"]
        if m["claimant"] not in claimants:
            errors.append(f"CODE: moves {mid} claimant {m['claimant']!r}")
        if m["status"] not in schema.MOVE_STATUS:
            errors.append(f"CODE: moves {mid} status {m['status']!r}")
        if m["coded_by"] not in schema.CODED_BY:
            errors.append(f"CODE: moves {mid} coded_by {m['coded_by']!r}")
        if m["intensification_criterion"] not in schema.INTENSIFICATION_CRITERIA:
            errors.append(f"CODE: moves {mid} intensification_criterion {m['intensification_criterion']!r}")
        for f in schema.FLAG_COLUMNS:
            if m[f] not in ("0", "1"):
                errors.append(f"CODE: moves {mid} {f} {m[f]!r} (expected 0/1)")
        if not m["year"].isdigit():
            errors.append(f"CODE: moves {mid} year {m['year']!r}")
        for code in m["dyads"].split():
            if not (1 <= len(code) <= 2) or not set(code) <= schema.DYAD_LETTERS:
                errors.append(f"CODE: moves {mid} dyad {code!r}")
        if not any(m[t] == "1" for t in schema.TYPE_FLAGS):
            errors.append(f"NO_TYPE: moves {mid} has no Type flag set")

    move_ids = {m["move_id"] for m in moves}
    events = tables["events"]
    for e in events:
        eid = e["event_id"]
        if e["status"] not in schema.EVENT_STATUS:
            errors.append(f"CODE: events {eid} status {e['status']!r}")
        if e["claimant"] not in claimants:
            errors.append(f"CODE: events {eid} claimant {e['claimant']!r}")
        if e["date_precision"] and e["date_precision"] not in schema.DATE_PRECISION:
            errors.append(f"CODE: events {eid} date_precision {e['date_precision']!r}")
        if e["location_precision"] and e["location_precision"] not in schema.LOCATION_PRECISION:
            errors.append(f"CODE: events {eid} location_precision {e['location_precision']!r}")
        if e["subregion"] and e["subregion"] not in {str(i) for i in range(1, 11)}:
            errors.append(f"CODE: events {eid} subregion {e['subregion']!r}")
        if e["status"] != "candidate" and e["move_id"] not in move_ids:
            errors.append(f"EVENT_MOVE: events {eid} ({e['status']}) move_id {e['move_id']!r} does not exist")

    event_ids = {e["event_id"] for e in events}
    sourced = Counter()
    for s in tables["sources"]:
        if s["event_id"] not in event_ids:
            errors.append(f"SOURCE_EVENT: sources {s['source_id']} event_id {s['event_id']!r} does not exist")
        sourced[s["event_id"]] += 1
    for e in events:
        if e["status"] == "accepted" and not sourced[e["event_id"]]:
            errors.append(f"EVENT_NO_SOURCE: events {e['event_id']} is accepted but has no source")

    if xlsx_path is not None:
        errors += comparability(moves, tables["corrections"], Path(xlsx_path))
    return errors


def comparability(moves: list[dict], corrections: list[dict], xlsx_path: Path) -> list[str]:
    errors = []
    expected = read_mats_xlsx(xlsx_path)
    ours = {m["move_id"]: m for m in moves if m["coded_by"] == "chubb" and m["status"] == "accepted"
            and m["data_version"] == "1.02"}
    corrected = {(c["move_id"], c["field"]): c["new_value"] for c in corrections}

    missing = sorted(set(expected) - set(ours))
    extra = sorted(set(ours) - set(expected))
    if missing:
        errors.append(f"COMPARABILITY: MATS 1.02 moves missing from moves.csv: {missing[:10]}{'...' if len(missing) > 10 else ''}")
    if extra:
        errors.append(f"COMPARABILITY: moves claim data_version 1.02 but are not in MATS 1.02: {extra[:10]}")

    exp_cy = Counter((r["claimant"], r["year"]) for r in expected.values())
    our_cy = Counter((m["claimant"], m["year"]) for m in ours.values())
    for key in sorted(set(exp_cy) | set(our_cy)):
        if exp_cy[key] != our_cy[key]:
            errors.append(f"COMPARABILITY: {key[0]} {key[1]} has {our_cy[key]} moves, MATS 1.02 has {exp_cy[key]}")
    for t in schema.TYPE_FLAGS:
        a = sum(r[t] == "1" for r in expected.values())
        b = sum(m[t] == "1" for m in ours.values())
        if a != b:
            errors.append(f"COMPARABILITY: Type total {t} is {b}, MATS 1.02 has {a}")

    for mid in sorted(set(expected) & set(ours)):
        for col in XLSX_FIELDS:
            want = corrected.get((mid, col), expected[mid][col])
            if ours[mid][col] != want:
                errors.append(f"COMPARABILITY: {mid}.{col} differs from MATS 1.02 and no correction is documented")
    return errors


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--xlsx", type=Path, default=Path("data/raw/mats-1.02/MATS_1-02_all_cases.xlsx"))
    a = p.parse_args(argv)
    errors = validate(a.data, a.xlsx)
    for e in errors:
        print(e)
    n_moves = len(_read_csv(a.data / "moves.csv")[1]) if (a.data / "moves.csv").exists() else 0
    print(f"{'FAIL' if errors else 'OK'}: {len(errors)} error(s); {n_moves} moves checked")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
