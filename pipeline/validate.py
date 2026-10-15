"""Validate the canonical files. Exit 1 with one line per error; exit 0 when clean.

Rules (docs/spec.md, "Validator"):
  SCHEMA          columns of each table are exactly the schema's
  CODE            codes within allowed sets (claimant, status, precision, flags 0/1, dyad letters)
  NO_TYPE         a move must have at least one Type flag
  EVENT_MOVE      an accepted or merged event must point at an existing move of the same claimant
                  and year; a candidate or rejected event may have none, but never a dangling one
  DATE            event dates are ISO dates, end >= start; lat/lon numeric and in range
  LOCATION        a point event has both coordinates (a feature event names a feature; it has them
                  when the gazetteer knows the name); a located event's sub-region, when stated, is
                  the one its coordinates fall in (data/reference/mavd_subregions.geojson)
  SOURCE_EVENT    a source must point at an existing event
  EVENT_NO_SOURCE an accepted event must have at least one source
  DUPLICATE       identifiers are unique
  COMPARABILITY   accepted CN/VN/PH moves for 1970-2015 equal MATS 1.02: counts per claimant-year
                  and Type totals over ALL accepted moves in that scope (whoever coded them), and
                  every xlsx field of every coded_by=chubb row (plus the two MAVD-only columns),
                  apart from corrections documented in corrections.csv. Packed codes are a
                  function of the flags, so the field-by-field check covers them.
  (CODE also covers corrections.csv rows: known move, known field.)

The comparability check reads the raw inputs with its own small reader, independent of the loader.
aggregates() and event_aggregates() compute the chart and map numbers independently of the site
build (seam 3).

Usage: python -m pipeline.validate [--data DIR] [--xlsx FILE] [--mavd FILE]
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from pipeline import gazetteer, schema

ROOT = Path(__file__).resolve().parents[1]
XLSX_FIELDS = schema.MATS_XLSX_COLUMNS
GUARDED_FIELDS = list(XLSX_FIELDS) + list(schema.MAVD_EXTRA_COLUMNS)


def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def _is_iso_date(s: str) -> bool:
    import datetime as _dt
    try:
        _dt.date.fromisoformat(s)
        return len(s) == 10
    except ValueError:
        return False


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
    rows = list(wb[schema.MATS_XLSX_SHEET].iter_rows(values_only=True))
    header = rows[0]
    idx = header.index(schema.MATS_XLSX_ID)
    out = {}
    for r in rows[1:]:
        if not r[idx]:
            continue
        d = dict(zip(header, r))
        rec = {}
        for col, xcol in XLSX_FIELDS.items():
            v = d[xcol]
            if col in schema.FLAG_COLUMNS:
                if _norm(v) not in ("", "0", "1"):
                    raise ValueError(f"MATS 1.02 {d[schema.MATS_XLSX_ID]} {xcol}: flag value {v!r} is not 0/1")
                rec[col] = "1" if _norm(v) == "1" else "0"
            else:
                rec[col] = _norm(v)
        out[_norm(d[schema.MATS_XLSX_ID])] = rec
    return out


def read_mavd_extras(path: Path) -> dict[str, dict]:
    """The MAVD-only columns per move, normalised like the loader does."""
    with open(path, newline="", encoding="utf-8") as f:
        return {r["AltCaseNo"]: {col: r[src].strip() for col, src in schema.MAVD_EXTRA_COLUMNS.items()}
                for r in csv.DictReader(f) if r["AltCaseNo"]}


def validate(data_dir: Path, xlsx_path: Path | None, mavd_path: Path | None = None) -> list[str]:
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
        if m["coded_by"] == "project" and not m["intensification_criterion"]:
            errors.append(f"CODE: moves {mid} is project-coded without an intensification_criterion")
        if m["intensification_criterion"] and m["intensification_criterion"] not in schema.INTENSIFICATION_CRITERIA:
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
    move_by_id = {m["move_id"]: m for m in moves}
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
        if e["move_id"] and e["move_id"] not in move_ids:
            errors.append(f"EVENT_MOVE: events {eid} ({e['status']}) move_id {e['move_id']!r} does not exist")
        elif e["status"] in ("accepted", "merged") and not e["move_id"]:
            errors.append(f"EVENT_MOVE: events {eid} ({e['status']}) has no move")
        elif e["move_id"]:
            mv = move_by_id[e["move_id"]]
            if mv["claimant"] != e["claimant"]:
                errors.append(f"EVENT_MOVE: events {eid} claimant {e['claimant']} but move {e['move_id']} is {mv['claimant']}")
            elif (e["status"] in ("accepted", "merged") and e["date_start"][:4] != mv["year"]
                  and e["harvest_run_id"] != "seed-mats-1.02"):   # three MAVD seed dates are known typos, logged for the author
                errors.append(f"EVENT_MOVE: events {eid} dated {e['date_start']} but move {e['move_id']} is {mv['year']}")
        if e["status"] == "rejected" and not e["review_note"]:
            errors.append(f"CODE: events {eid} is rejected without a review note")
        for col in ("date_start", "date_end"):
            if e[col] and not _is_iso_date(e[col]):
                errors.append(f"DATE: events {eid} {col} {e[col]!r} is not an ISO date")
        if e["date_start"] and e["date_end"] and _is_iso_date(e["date_start"]) and _is_iso_date(e["date_end"]) and e["date_end"] < e["date_start"]:
            errors.append(f"DATE: events {eid} ends before it starts")
        coords = {}
        for col, lo, hi in (("lat", -90.0, 90.0), ("lon", -180.0, 180.0)):
            if e[col]:
                try:
                    v = float(e[col])
                except ValueError:
                    v = None
                if v is None or not lo <= v <= hi:
                    errors.append(f"DATE: events {eid} {col} {e[col]!r} is not a coordinate")
                else:
                    coords[col] = v
        if e["location_precision"] == "point" and len(coords) < 2:
            errors.append(f"LOCATION: events {eid} is a point but lacks coordinates")
        if len(coords) == 2 and e["subregion"]:
            actual = gazetteer.subregion_of(coords["lat"], coords["lon"])
            if actual and str(actual) != e["subregion"]:
                errors.append(f"LOCATION: events {eid} says subregion {e['subregion']} but ({e['lat']}, {e['lon']}) lies in {actual}")

    event_ids = {e["event_id"] for e in events}
    sourced = Counter()
    for s in tables["sources"]:
        if s["event_id"] not in event_ids:
            errors.append(f"SOURCE_EVENT: sources {s['source_id']} event_id {s['event_id']!r} does not exist")
        sourced[s["event_id"]] += 1
    for e in events:
        if e["status"] == "accepted" and not sourced[e["event_id"]]:
            errors.append(f"EVENT_NO_SOURCE: events {e['event_id']} is accepted but has no source")

    for c in tables["corrections"]:
        if c["move_id"] not in move_ids:
            errors.append(f"CODE: corrections move_id {c['move_id']!r} does not exist")
        if c["field"] not in GUARDED_FIELDS:
            errors.append(f"CODE: corrections field {c['field']!r} is not a guarded field")

    if xlsx_path is not None:
        errors += comparability(moves, tables["corrections"], Path(xlsx_path),
                                Path(mavd_path) if mavd_path else None)
    return errors


def comparability(moves: list[dict], corrections: list[dict], xlsx_path: Path,
                  mavd_path: Path | None = None) -> list[str]:
    errors = []
    expected = read_mats_xlsx(xlsx_path)
    corrected = {(c["move_id"], c["field"]): c["new_value"] for c in corrections}

    # Counts: every accepted move in MATS's scope counts, whoever coded it (ADR 0001).
    in_scope = {m["move_id"]: m for m in moves if m["status"] == "accepted"
                and m["claimant"] in schema.MATS_CLAIMANTS and m["year"].isdigit()
                and int(m["year"]) in schema.MATS_YEARS}
    exp_cy = Counter((r["claimant"], r["year"]) for r in expected.values())
    our_cy = Counter((m["claimant"], m["year"]) for m in in_scope.values())
    for key in sorted(set(exp_cy) | set(our_cy)):
        if exp_cy[key] != our_cy[key]:
            errors.append(f"COMPARABILITY: {key[0]} {key[1]} has {our_cy[key]} accepted moves, MATS 1.02 has {exp_cy[key]}")
    for t in schema.TYPE_FLAGS:
        a = sum(r[t] == "1" for r in expected.values())
        b = sum(m[t] == "1" for m in in_scope.values())
        if a != b:
            errors.append(f"COMPARABILITY: Type total {t} is {b}, MATS 1.02 has {a}")

    # Rows: every MATS 1.02 move is present as coded_by=chubb and field-identical, bar documented corrections.
    chubb = {m["move_id"]: m for m in moves if m["coded_by"] == "chubb" and m["data_version"] == "1.02"}
    missing = sorted(set(expected) - set(chubb))
    extra = sorted(set(chubb) - set(expected))
    if missing:
        errors.append(f"COMPARABILITY: MATS 1.02 moves missing from moves.csv: {missing[:10]}{'...' if len(missing) > 10 else ''}")
    if extra:
        errors.append(f"COMPARABILITY: moves claim data_version 1.02 but are not in MATS 1.02: {extra[:10]}")
    for mid in sorted(set(expected) & set(chubb)):
        if chubb[mid]["status"] != "accepted":
            errors.append(f"COMPARABILITY: {mid} is a MATS 1.02 move but status is {chubb[mid]['status']!r}")
        for col in XLSX_FIELDS:
            want = corrected.get((mid, col), expected[mid][col])
            if chubb[mid][col] != want:
                errors.append(f"COMPARABILITY: {mid}.{col} differs from MATS 1.02 and no correction is documented")
    if mavd_path is not None:
        extras = read_mavd_extras(mavd_path)
        for mid in sorted(set(extras) & set(chubb)):
            for col in schema.MAVD_EXTRA_COLUMNS:
                want = corrected.get((mid, col), extras[mid][col])
                if chubb[mid][col] != want:
                    errors.append(f"COMPARABILITY: {mid}.{col} differs from the MAVD table and no correction is documented")
    return errors


# ---------------------------------------------------------------------------
# Aggregates: the numbers the site's charts draw, computed here independently of
# the site build so a test can hold the two to the same answer (seam 3).

def aggregates(moves: list[dict]) -> dict:
    """Counts of accepted moves per claimant and year for every flag, and per sub-region cross-tabs.

    Years run 1970..latest accepted move. Flags other than Type are non-exclusive, so their
    sums are mentions, not moves; "total" is always the number of moves. Per-year rows carry the
    Type, Domain and Issue flags; sub-region counts per year live in the sparse "subregion_years".
    """
    accepted = [m for m in moves if m["status"] == "accepted"]
    last = max((int(m["year"]) for m in accepted), default=1970)
    years = list(range(1970, max(last, 1970) + 1))
    out = {"years": years, "types": list(schema.TYPE_FLAGS), "domains": list(schema.DOMAIN_FLAGS),
           "issues": list(schema.ISSUE_FLAGS), "subregions": list(schema.SUBREGION_FLAGS),
           "claimants": list(schema.CLAIMANT_CODES),
           "n_moves": len(accepted), "n_pending": sum(1 for m in moves if m["status"] == "pending"),
           "by_claimant": {}}
    dims = schema.TYPE_FLAGS + schema.DOMAIN_FLAGS + schema.ISSUE_FLAGS
    for c in schema.CLAIMANT_CODES:
        per_year = {str(y): {**{f: 0 for f in dims}, "total": 0} for y in years}
        per_loc = {str(i + 1): {**{f: 0 for f in dims}, "total": 0} for i in range(len(schema.SUBREGION_FLAGS))}
        loc_years: dict[str, dict] = {str(i + 1): {} for i in range(len(schema.SUBREGION_FLAGS))}  # sparse: years with moves
        for m in accepted:
            if m["claimant"] != c:
                continue
            row = per_year[m["year"]]
            row["total"] += 1
            for f in dims:
                if m[f] == "1":
                    row[f] += 1
            for i, loc in enumerate(schema.SUBREGION_FLAGS):
                if m[loc] == "1":
                    cell = per_loc[str(i + 1)]
                    cell["total"] += 1
                    for f in dims:
                        if m[f] == "1":
                            cell[f] += 1
                    ly = loc_years[str(i + 1)].setdefault(m["year"], {**{t_: 0 for t_ in schema.TYPE_FLAGS}, "total": 0})
                    ly["total"] += 1
                    for t_ in schema.TYPE_FLAGS:
                        if m[t_] == "1":
                            ly[t_] += 1
        totals = {f: sum(r[f] for r in per_year.values()) for f in dims}
        for i, loc in enumerate(schema.SUBREGION_FLAGS):
            totals[loc] = per_loc[str(i + 1)]["total"]
        totals["total"] = sum(r["total"] for r in per_year.values())
        out["by_claimant"][c] = {"years": per_year, "totals": totals, "subregions": per_loc, "subregion_years": loc_years}
    return out


def map_subregions(e: dict, move: dict) -> list[str]:
    """Where an event without coordinates counts on the map: its own sub-region if stated, else every
    sub-region of its move (MATS-era seed events carry no location of their own)."""
    if e["subregion"]:
        return [e["subregion"]]
    return [str(i + 1) for i, f in enumerate(schema.SUBREGION_FLAGS) if move[f] == "1"]


def event_aggregates(events: list[dict], moves: list[dict]) -> dict:
    """The map's numbers: accepted events of accepted moves, split into points (both coordinates)
    and sub-region counts (no coordinates; see map_subregions), per claimant and per year."""
    move_by_id = {m["move_id"]: m for m in moves if m["status"] == "accepted"}
    shown = [e for e in events if e["status"] == "accepted" and e["move_id"] in move_by_id]
    out = {"n_events": len(shown), "n_points": 0, "by_claimant": {}}
    for c in schema.CLAIMANT_CODES:
        cc = {"events": 0, "points": 0, "subregions": {str(i): 0 for i in range(1, 11)}, "years": {}}
        for e in shown:
            if e["claimant"] != c:
                continue
            cc["events"] += 1
            y = e["date_start"][:4] or move_by_id[e["move_id"]]["year"]
            cc["years"][y] = cc["years"].get(y, 0) + 1
            if e["lat"] and e["lon"]:
                cc["points"] += 1
            else:
                for sr in map_subregions(e, move_by_id[e["move_id"]]):
                    cc["subregions"][sr] += 1
        out["n_points"] += cc["points"]
        out["by_claimant"][c] = cc
    return out

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=ROOT / "data")
    p.add_argument("--xlsx", type=Path, default=ROOT / "data/raw/mats-1.02/MATS_1-02_all_cases.xlsx")
    p.add_argument("--mavd", type=Path, default=ROOT / "data/raw/mavd-arcgis-2023/All_Actions7.csv")
    a = p.parse_args(argv)
    errors = validate(a.data, a.xlsx, a.mavd)
    for e in errors:
        print(e)
    print(f"{'FAIL' if errors else 'OK'}: {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
