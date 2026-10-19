"""Build the canonical tables from MATS 1.02 (author's xlsx) and the MAVD online table.

Rules (docs/spec.md, "Loading MATS 1.02"):
- The xlsx is authoritative for the 357 CN/VN/PH moves 1970-2015 (coded_by=chubb, data_version=1.02).
- From the MAVD table: diminished cases, other possible cases, and Dates are imported.
  Each ';'-separated date token becomes one seed event with one source (the MATS description).
- VN197304 (online only) is loaded with status=pending, data_version=mavd-2023.
- Every description or flag difference between xlsx and MAVD is logged; the xlsx value is used.

Usage: python -m pipeline.load_mats [--out data]
"""
from __future__ import annotations

import argparse
import calendar
import csv
import re
from pathlib import Path

import openpyxl

from pipeline import schema

ROOT = Path(__file__).resolve().parents[1]
XLSX_FLAG_MAP = {x: c for c, x in schema.MATS_XLSX_COLUMNS.items() if c in schema.FLAG_COLUMNS}
MAVD_FLAG_MAP = {
    "Declarative": "declarative", "Demonstrative": "demonstrative", "Coercive": "coercive", "Force": "force",
    "Domain1": "domestic", "Domain2": "diplomatic", "Domain3": "physical",
    "Issue1": "military", "Issue2": "administrative", "Issue3": "energy", "Issue4": "fisheries", "Issue5": "politics",
    **{f"Loc{i}": schema.SUBREGION_FLAGS[i - 1] for i in range(1, 11)},
}
# Frozen provenance values for seed events, so the loader is reproducible run after run.
SEED_RUN = "seed-mats-1.02"
MATS_CITATION = 'Chubb, A. (2022), "Maritime Assertiveness Time Series (MATS 1.0)" dataset, version 1.02'
MATS_PUB_DATE = "2022"
MATS_ACCESSED = "2026-10"           # when the xlsx was received from the author
MAVD_SERVICE_DATE = "2022-05-14"    # MAVD0514227 feature service: the Dates column's provenance
SEED_REVIEWER = "Andrew Chubb"      # the dates are his (MAVD); the loader only transcribes them


def _flag(v, where: str = "") -> str:
    """0/1 flag cell. Blank counts as 0; anything else than 0 or 1 is an error, never coerced."""
    if v in (None, "", "None"):
        return "0"
    s = str(v).strip()
    if s in ("0", "0.0"):
        return "0"
    if s in ("1", "1.0"):
        return "1"
    raise ValueError(f"flag value {v!r} is not 0/1 ({where})")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def read_xlsx(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True)
    rows = list(wb[schema.MATS_XLSX_SHEET].iter_rows(values_only=True))
    header = rows[0]
    idx = header.index(schema.MATS_XLSX_ID)
    return [dict(zip(header, r)) for r in rows[1:] if r[idx]]


def read_mavd(path: Path) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return {r["AltCaseNo"]: r for r in csv.DictReader(f) if r["AltCaseNo"]}


def _blank_move() -> dict:
    return {c: "" for c in schema.TABLES["moves"]}


def move_from_xlsx(r: dict) -> dict:
    m = _blank_move()
    m.update(
        move_id=_s(r["AltCaseNo"]), claimant=_s(r["CountryCode"]), year=str(r["Year"]),
        instance_no=str(int(_s(r["AltCaseNo"])[-2:])),
        dyads=_s(r["Dyads"]), description=_s(r["Case description and sources"]),
        ongoing_through=_s(r["Ongoing through"]), ongoing_through_notes=_s(r["Ongoing through notes"]),
        org_case_no=_s(r["OrgCaseNo"]),
        coded_by="chubb", coder="Andrew Chubb", coding_date="", data_version="1.02", status="accepted",
    )
    for src, dst in XLSX_FLAG_MAP.items():
        m[dst] = _flag(r[src], f"xlsx {m['move_id']} {src}")
    return m


def move_from_mavd(r: dict) -> dict:
    m = _blank_move()
    m.update(
        move_id=r["AltCaseNo"], claimant=r["CountryCode"], year=r["Year"],
        instance_no=str(int(r["AltCaseNo"][-2:])),
        dyads=_s(r["Dyads"]), description=_s(r["Intensified_assertive_actions"]),
        ongoing_through=_s(r["Ongoing_through"]), ongoing_through_notes=_s(r["Ongoing_through_notes"]),
        org_case_no=_s(r["OrgCaseNo"]),
        coded_by="chubb", coder="Andrew Chubb", coding_date="", data_version="mavd-2023", status="pending",
    )
    for src, dst in MAVD_FLAG_MAP.items():
        m[dst] = _flag(r[src], f"MAVD {m['move_id']} {src}")
    return m


DATE_RE = re.compile(r"^(~)?(\d{4})(?:/(\d{1,2}))?(?:/(\d{1,2}))?$")


def parse_date_token(token: str, where: str = "") -> tuple[str, str, str, bool]:
    """'1974/01/18' -> ('1974-01-18','1974-01-18','day',False); '~1975/10' -> month range, approximate."""
    t = token.strip()
    mt = DATE_RE.match(t)
    if not mt:
        raise ValueError(f"unrecognised date token {token!r} ({where})")
    approx, y, mo, d = mt.groups()
    if d:
        iso = f"{y}-{int(mo):02d}-{int(d):02d}"
        return iso, iso, "day", bool(approx)
    if mo:
        last = calendar.monthrange(int(y), int(mo))[1]
        return f"{y}-{int(mo):02d}-01", f"{y}-{int(mo):02d}-{last:02d}", "month", bool(approx)
    return f"{y}-01-01", f"{y}-12-31", "year", bool(approx)


def seed_events(move: dict, dates: str) -> tuple[list[dict], list[dict], list[dict]]:
    """One seed event per ';'-separated date token, each with one source (the MATS description).

    Returns (events, sources, anomalies); an anomaly is a date outside the move's year (a move is an
    intensification in that calendar year, so a seed date in another year is a likely typo in MAVD).
    Seed events of a pending move are candidates, not accepted.
    """
    events, sources, anomalies = [], [], []
    status = "accepted" if move["status"] == "accepted" else "candidate"
    year_of_move = int(move["year"])
    for n, token in enumerate(dates.split(";"), start=1):
        start, end, precision, approx = parse_date_token(token, f"MAVD Dates for {move['move_id']}")
        eid = f"{move['move_id']}-E{n:02d}"
        clean = token.strip().lstrip("~")
        summary = (
            f"Incident dated {clean} within move {move['move_id']}; "
            "seed event derived from the MAVD 'Dates' column, see the move description."
        )
        if approx:
            summary = "Approximate date. " + summary
        note = f"Date transcribed from the MAVD 'Dates' column ({MAVD_SERVICE_DATE} service)."
        if int(start[:4]) != year_of_move:
            anomalies.append({"move_id": move["move_id"], "event_id": eid, "date": clean, "move_year": str(year_of_move)})
            note += f" Outside the move's year ({year_of_move}); possible typo in MAVD, flagged for the author."
        e = {c: "" for c in schema.TABLES["events"]}
        e.update(
            event_id=eid, move_id=move["move_id"], claimant=move["claimant"],
            date_start=start, date_end=end, date_precision=precision,
            location_precision="unknown",
            summary=summary, status=status, harvest_run_id=SEED_RUN,
            reviewer=SEED_REVIEWER, review_date=MAVD_SERVICE_DATE, review_note=note,
        )
        events.append(e)
        s = {c: "" for c in schema.TABLES["sources"]}
        s.update(
            source_id=f"{eid}-S01", event_id=eid, url="", title=f"MATS 1.02 case description, {move['move_id']}",
            publisher=MATS_CITATION, pub_date=MATS_PUB_DATE, language="en", accessed_date=MATS_ACCESSED,
            excerpt=move["description"],
        )
        sources.append(s)
    return events, sources, anomalies


def load_tables(xlsx_path: Path, mavd_path: Path) -> dict:
    xlsx = read_xlsx(xlsx_path)
    mavd = read_mavd(mavd_path)
    moves, events, sources, differences, anomalies = [], [], [], [], []
    packed = {"Domains": schema.packed_domains, "Issues": schema.packed_issues, "Locations": schema.packed_locations}

    def add_seeds(m, o):
        if o["Dates"]:
            ev, so, an = seed_events(m, o["Dates"])
            events.extend(ev); sources.extend(so); anomalies.extend(an)

    for r in xlsx:
        m = move_from_xlsx(r)
        for name, fn in packed.items():  # xlsx-internal inconsistency: flags win, packed code logged
            if fn(m) != int(r[name]):
                differences.append({"kind": "xlsx-internal", "move_id": m["move_id"], "field": name,
                                    "xlsx": f"packed code {r[name]} vs flags {fn(m)}", "mavd": "n/a"})
        o = mavd.get(m["move_id"])
        if o:
            for dst, src in schema.MAVD_EXTRA_COLUMNS.items():
                m[dst] = _s(o[src])
            online_desc = _s(o["Intensified_assertive_actions"])
            if online_desc != m["description"]:
                differences.append({"kind": "description", "move_id": m["move_id"], "field": "description",
                                    "xlsx": m["description"], "mavd": online_desc})
            for src, dst in MAVD_FLAG_MAP.items():
                mv = _flag(o[src], f"MAVD {m['move_id']} {src}")
                if mv != m[dst]:
                    differences.append({"kind": "flag", "move_id": m["move_id"], "field": dst, "xlsx": m[dst], "mavd": mv})
            add_seeds(m, o)
        moves.append(m)

    known = {m["move_id"] for m in moves}
    for cid, o in mavd.items():
        if cid not in known:
            m = move_from_mavd(o)
            for dst, src in schema.MAVD_EXTRA_COLUMNS.items():
                m[dst] = _s(o[src])
            moves.append(m)
            add_seeds(m, o)

    moves.sort(key=lambda m: m["move_id"])
    events.sort(key=lambda e: e["event_id"])
    sources.sort(key=lambda s: s["source_id"])
    claimants = [{"code": c, "name": n} for c, n in schema.CLAIMANTS]
    return {"claimants": claimants, "moves": moves, "events": events, "sources": sources,
            "differences": differences, "anomalies": anomalies}


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def write_differences(path: Path, differences: list[dict], anomalies: list[dict]) -> None:
    lines = [
        "# MATS 1.02 (xlsx) vs. MAVD online table: differences",
        "",
        "Generated by `python -m pipeline.load_mats`. The xlsx value is what the canonical data holds; ",
        "the MAVD value is shown for the author's review. Flags: 1 = set, 0 = not set.",
        "",
    ]
    by_kind = {k: [d for d in differences if d["kind"] == k] for k in ("xlsx-internal", "flag", "description")}
    lines += [f"## Inconsistencies inside the xlsx ({len(by_kind['xlsx-internal'])})", "",
              "Packed code column disagrees with the 0/1 flag columns; the flags are what the canonical data holds.", "",
              "| move | packed column | xlsx |", "|---|---|---|"]
    lines += [f"| {d['move_id']} | {d['field']} | {d['xlsx']} |" for d in by_kind["xlsx-internal"]]
    lines += ["", f"## Flag differences, xlsx vs MAVD ({len(by_kind['flag'])})", "",
              "| move | field | xlsx | MAVD |", "|---|---|---|---|"]
    lines += [f"| {d['move_id']} | {d['field']} | {d['xlsx']} | {d['mavd']} |" for d in by_kind["flag"]]
    lines += ["", f"## Seed-event dates outside the move's year ({len(anomalies)})", "",
              "From the MAVD `Dates` column; transcribed as given and flagged in the event's review note.", "",
              "| move | event | date | move year |", "|---|---|---|---|"]
    lines += [f"| {a['move_id']} | {a['event_id']} | {a['date']} | {a['move_year']} |" for a in anomalies]
    lines += ["", f"## Description differences ({len(by_kind['description'])})", ""]
    for d in by_kind["description"]:
        lines += [f"### {d['move_id']}", "", "**xlsx:**", "", d["xlsx"], "", "**MAVD:**", "", d["mavd"], ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def check_mats_rows(data_dir: Path, tables: dict) -> list[str]:
    """The MATS-era rows in the canonical files equal what the loader produces from the raw inputs:
    every move the loader makes (chubb-coded, plus the pending one), the seed events, their sources
    and the claimants, field for field. Project-coded rows and harvested events are not the
    loader's and are ignored, so a review branch or an accepted harvest passes."""
    import csv

    def rows(name):
        with open(data_dir / f"{name}.csv", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    errors = []
    expect_moves = {m["move_id"]: m for m in tables["moves"]}
    have_moves = {m["move_id"]: m for m in rows("moves") if m["move_id"] in expect_moves}
    for mid, m in expect_moves.items():
        if mid not in have_moves:
            errors.append(f"move {mid} from the raw inputs is missing")
        elif have_moves[mid] != m:
            errors.append(f"move {mid} differs from the raw inputs: " + ", ".join(k for k in m if have_moves[mid].get(k) != m[k]))
    expect_events = {e["event_id"]: e for e in tables["events"]}
    have_events = {e["event_id"]: e for e in rows("events") if e["event_id"] in expect_events}
    for eid, e in expect_events.items():
        if eid not in have_events:
            errors.append(f"seed event {eid} is missing")
        elif have_events[eid] != e:
            errors.append(f"seed event {eid} differs: " + ", ".join(k for k in e if have_events[eid].get(k) != e[k]))
    expect_sources = {s["source_id"]: s for s in tables["sources"]}
    have_sources = {s["source_id"]: s for s in rows("sources") if s["source_id"] in expect_sources}
    for sid, s_ in expect_sources.items():
        if have_sources.get(sid) != s_:
            errors.append(f"seed source {sid} is missing or differs")
    if rows("claimants") != tables["claimants"]:
        errors.append("claimants.csv differs from the loader's")
    return errors


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--xlsx", type=Path, default=ROOT / "data/raw/mats-1.02/MATS_1-02_all_cases.xlsx")
    p.add_argument("--mavd", type=Path, default=ROOT / "data/raw/mavd-arcgis-2023/All_Actions7.csv")
    p.add_argument("--out", type=Path, default=ROOT / "data")
    p.add_argument("--diff-log", type=Path, default=ROOT / "docs/reports/mats-1.02-vs-mavd-differences.md")
    p.add_argument("--check", type=Path, default=None, help="do not write; check that DIR's MATS-era rows equal the loader's output")
    a = p.parse_args(argv)
    t = load_tables(a.xlsx, a.mavd)
    if a.check:
        errors = check_mats_rows(a.check, t)
        for e in errors:
            print(e)
        print(f"{'OK' if not errors else 'FAILED'}: MATS-era rows in {a.check} {'equal' if not errors else 'differ from'} the raw inputs "
              f"({len(t['moves'])} moves, {len(t['events'])} seed events, {len(t['sources'])} seed sources)")
        raise SystemExit(1 if errors else 0)
    a.out.mkdir(parents=True, exist_ok=True)
    for name in ("claimants", "moves", "events", "sources"):
        write_csv(a.out / f"{name}.csv", t[name], schema.TABLES[name])
    corrections = a.out / "corrections.csv"
    if not corrections.exists():
        write_csv(corrections, [], schema.TABLES["corrections"])
    a.diff_log.parent.mkdir(parents=True, exist_ok=True)
    write_differences(a.diff_log, t["differences"], t["anomalies"])
    print(f"moves {len(t['moves'])}, events {len(t['events'])}, sources {len(t['sources'])}, "
          f"differences {len(t['differences'])}, date anomalies {len(t['anomalies'])} -> {a.out}/")


if __name__ == "__main__":
    main()
