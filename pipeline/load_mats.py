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

XLSX_FLAG_MAP = {
    "Declarative": "declarative", "Demonstrative": "demonstrative", "Coercive": "coercive", "Force": "force",
    "Domestic": "domestic", "Diplomatic": "diplomatic", "Physical": "physical",
    "Military": "military", "Administrative": "administrative", "Energy": "energy",
    "Fisheries": "fisheries", "Politics": "politics",
    "Tonkin": "loc01_tonkin", "Paracels": "loc02_paracels", "CentralWest": "loc03_central_west",
    "CentralEast": "loc04_central_east", "SpratlyNW": "loc05_spratly_nw", "SpratlyNE": "loc06_spratly_ne",
    "SpratlySE": "loc07_spratly_se", "SpratlySW": "loc08_spratly_sw", "NamConSon": "loc09_nam_con_son",
    "FarSouth": "loc10_far_south",
}
MAVD_FLAG_MAP = {
    "Declarative": "declarative", "Demonstrative": "demonstrative", "Coercive": "coercive", "Force": "force",
    "Domain1": "domestic", "Domain2": "diplomatic", "Domain3": "physical",
    "Issue1": "military", "Issue2": "administrative", "Issue3": "energy", "Issue4": "fisheries", "Issue5": "politics",
    **{f"Loc{i}": schema.SUBREGION_FLAGS[i - 1] for i in range(1, 11)},
}
SEED_RUN = "seed-mats-1.02"
MATS_CITATION = 'Chubb, A. (2022), "Maritime Assertiveness Time Series (MATS 1.0)" dataset, version 1.02'


def _flag(v) -> str:
    if v in (None, "", "None"):
        return "0"
    return "1" if int(float(v)) else "0"


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def read_xlsx(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True)
    rows = list(wb["MATS 1.02 cases"].iter_rows(values_only=True))
    header = rows[0]
    return [dict(zip(header, r)) for r in rows[1:] if r[2]]


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
        m[dst] = _flag(r[src])
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
        m[dst] = _flag(r[src])
    return m


DATE_RE = re.compile(r"^(~)?(\d{4})(?:/(\d{1,2}))?(?:/(\d{1,2}))?$")


def parse_date_token(token: str) -> tuple[str, str, str, bool]:
    """'1974/01/18' -> ('1974-01-18','1974-01-18','day',False); '~1975/10' -> month range, approximate."""
    t = token.strip()
    mt = DATE_RE.match(t)
    if not mt:
        raise ValueError(f"unrecognised date token: {token!r}")
    approx, y, mo, d = mt.groups()
    if d:
        iso = f"{y}-{int(mo):02d}-{int(d):02d}"
        return iso, iso, "day", bool(approx)
    if mo:
        last = calendar.monthrange(int(y), int(mo))[1]
        return f"{y}-{int(mo):02d}-01", f"{y}-{int(mo):02d}-{last:02d}", "month", bool(approx)
    return f"{y}-01-01", f"{y}-12-31", "year", bool(approx)


def seed_events(move: dict, dates: str) -> tuple[list[dict], list[dict]]:
    events, sources = [], []
    subregions = [i + 1 for i, f in enumerate(schema.SUBREGION_FLAGS) if move[f] == "1"]
    for n, token in enumerate(dates.split(";"), start=1):
        start, end, precision, approx = parse_date_token(token)
        eid = f"{move['move_id']}-E{n:02d}"
        summary = (
            f"Incident dated {token.strip().lstrip('~')} within move {move['move_id']}; "
            "seed event derived from the MAVD 'Dates' column, see the move description."
        )
        if approx:
            summary = "Approximate date. " + summary
        e = {c: "" for c in schema.TABLES["events"]}
        e.update(
            event_id=eid, move_id=move["move_id"], claimant=move["claimant"],
            date_start=start, date_end=end, date_precision=precision,
            location_precision="subregion" if len(subregions) == 1 else "unknown",
            subregion=str(subregions[0]) if len(subregions) == 1 else "",
            summary=summary, status="accepted", harvest_run_id=SEED_RUN, reviewer="loader", review_date="",
        )
        events.append(e)
        s = {c: "" for c in schema.TABLES["sources"]}
        s.update(
            source_id=f"{eid}-S01", event_id=eid, url="", title=f"MATS 1.02 case description, {move['move_id']}",
            publisher=MATS_CITATION, pub_date="2022", language="en", accessed_date="2026-10",
            excerpt=move["description"],
        )
        sources.append(s)
    return events, sources


def load_tables(xlsx_path: Path, mavd_path: Path) -> dict:
    xlsx = read_xlsx(xlsx_path)
    mavd = read_mavd(mavd_path)
    moves, events, sources, differences = [], [], [], []

    for r in xlsx:
        m = move_from_xlsx(r)
        for name, fn in (("Domains", schema.packed_domains), ("Issues", schema.packed_issues),
                         ("Locations", schema.packed_locations)):
            if fn(m) != int(r[name]):  # xlsx-internal inconsistency: flags win, packed code logged
                differences.append({"move_id": m["move_id"], "field": name,
                                    "xlsx": f"packed code {r[name]} vs flags {fn(m)}", "mavd": "n/a"})
        o = mavd.get(m["move_id"])
        if o:
            m["diminished_notes"] = _s(o["Cases_of_diminished_assertive_a"])
            m["other_possible_cases"] = _s(o["Other_Possible_Cases"])
            online_desc = _s(o["Intensified_assertive_actions"])
            if online_desc != m["description"]:
                differences.append({"move_id": m["move_id"], "field": "description",
                                    "xlsx": m["description"], "mavd": online_desc})
            for src, dst in MAVD_FLAG_MAP.items():
                if _flag(o[src]) != m[dst]:
                    differences.append({"move_id": m["move_id"], "field": dst, "xlsx": m[dst], "mavd": _flag(o[src])})
            if o["Dates"]:
                ev, so = seed_events(m, o["Dates"])
                events.extend(ev)
                sources.extend(so)
        moves.append(m)

    known = {m["move_id"] for m in moves}
    for cid, o in mavd.items():
        if cid not in known:
            m = move_from_mavd(o)
            moves.append(m)
            if o["Dates"]:
                ev, so = seed_events(m, o["Dates"])
                events.extend(ev)
                sources.extend(so)

    moves.sort(key=lambda m: m["move_id"])
    events.sort(key=lambda e: e["event_id"])
    sources.sort(key=lambda s: s["source_id"])
    claimants = [{"code": c, "name": n} for c, n in schema.CLAIMANTS]
    return {"claimants": claimants, "moves": moves, "events": events, "sources": sources, "differences": differences}


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def write_differences(path: Path, differences: list[dict]) -> None:
    lines = [
        "# MATS 1.02 (xlsx) vs. MAVD online table: differences",
        "",
        "Generated by `python -m pipeline.load_mats`. The xlsx value is what the canonical data holds; ",
        "the MAVD value is shown for the author's review. Flags: 1 = set, 0 = not set.",
        "",
    ]
    internal = [d for d in differences if d["field"] in ("Domains", "Issues", "Locations")]
    flags = [d for d in differences if d["field"] not in ("description", "Domains", "Issues", "Locations")]
    descs = [d for d in differences if d["field"] == "description"]
    lines += [f"## Inconsistencies inside the xlsx ({len(internal)})", "",
              "Packed code column disagrees with the 0/1 flag columns; the flags are what the canonical data holds.", "",
              "| move | packed column | xlsx |", "|---|---|---|"]
    lines += [f"| {d['move_id']} | {d['field']} | {d['xlsx']} |" for d in internal]
    lines += ["", f"## Flag differences, xlsx vs MAVD ({len(flags)})", "", "| move | field | xlsx | MAVD |", "|---|---|---|---|"]
    lines += [f"| {d['move_id']} | {d['field']} | {d['xlsx']} | {d['mavd']} |" for d in flags]
    lines += ["", f"## Description differences ({len(descs)})", ""]
    for d in descs:
        lines += [f"### {d['move_id']}", "", "**xlsx:**", "", d["xlsx"], "", "**MAVD:**", "", d["mavd"], ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--xlsx", type=Path, default=Path("data/raw/mats-1.02/MATS_1-02_all_cases.xlsx"))
    p.add_argument("--mavd", type=Path, default=Path("data/raw/mavd-arcgis-2023/All_Actions7.csv"))
    p.add_argument("--out", type=Path, default=Path("data"))
    p.add_argument("--diff-log", type=Path, default=Path("docs/reports/mats-1.02-vs-mavd-differences.md"))
    a = p.parse_args(argv)
    t = load_tables(a.xlsx, a.mavd)
    a.out.mkdir(parents=True, exist_ok=True)
    for name in ("claimants", "moves", "events", "sources"):
        write_csv(a.out / f"{name}.csv", t[name], schema.TABLES[name])
    corrections = a.out / "corrections.csv"
    if not corrections.exists():
        write_csv(corrections, [], schema.TABLES["corrections"])
    a.diff_log.parent.mkdir(parents=True, exist_ok=True)
    write_differences(a.diff_log, t["differences"])
    print(f"moves {len(t['moves'])}, events {len(t['events'])}, sources {len(t['sources'])}, "
          f"differences {len(t['differences'])} -> {a.out}/")


if __name__ == "__main__":
    main()
