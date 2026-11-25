"""Ticket 43: re-review — the audit's disagreements, decided by the maintainer in Airtable, applied to the data.

An audit (a long unattended session, docs/audit-prompt.md) reads every record the maintainer decided and
writes a *finding* wherever it would code the record differently: one record, one field, the current value,
the value it proposes, and why. Findings go to the base's Re-review table, one row each; the maintainer
answers each with keep (the current coding stands), take (the proposal) or edit (his own value), and a
sitting applies the answers to data/. Nothing changes without his answer (ADR 0003).

Scope. Only the project's own records: the moves coded by the project (coded_by = project) and the
harvested events the maintainer decided (accepted, rejected or merged). Chubb's moves are the benchmark
the audit compares against and are never changed here (ADR 0001).

    python -m pipeline.rereview rows  --findings F.json --audit AUDIT_ID --out batches.json [--data data]
    python -m pipeline.rereview apply --from export.json --date YYYY-MM-DD [--data data] [--out-dir DIR]

`rows` checks every finding against the data and writes the Airtable records in batches for the connector's
create call; `apply` reads the table as exported, applies the decided rows, archives them under
harvest/airtable/rereview/ and names the rows to clear. Neither command calls Airtable.

Fields a finding may address, and how their values are written (the same in Current, Proposed and
Your value):

  move   type            declarative | demonstrative | coercive | force
         domains         flag names, comma-separated: "domestic, physical"
         issues          flag names, comma-separated: "military, fisheries"
         subregions      sub-region numbers, comma-separated: "2, 5"
         dyads           Chubb's letter pairs, space-separated: "CV CP"
         intensification_criterion   novelty | frequency | scope
         ongoing_through a year
         description     free text
         withdraw        current "accepted"; proposed "withdraw": the move is removed and its accepted
                         events are rejected with it
  event  decision        current accepted | rejected | merged; proposed "reject", "accept into MOVE_ID"
                         or "reconsider" (back to candidate, for a fresh sitting)
         move            the move_id it belongs to; proposed another existing move
         date            "date_start | date_end | date_precision" (date_end may be empty)
         place           "location_name | lat | lon | location_precision | subregion"
         summary         free text
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from pipeline import schema
from pipeline.queue import read_table, write_table

CONFIG = Path(__file__).with_name("airtable.json")


def load_config() -> dict:
    """pipeline/airtable.json, read here rather than through pipeline.airtable, which nothing but the
    workbench imports (tests/test_airtable.py)."""
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def _plain(v):
    """A select value as its name, whichever shape the export gave it in."""
    if isinstance(v, dict):
        return v.get("name", "")
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v

MOVE_FIELDS = ["type", "domains", "issues", "subregions", "dyads", "intensification_criterion",
               "ongoing_through", "description", "withdraw"]
EVENT_FIELDS = ["decision", "move", "date", "place", "summary"]
FIELDS = {"move": MOVE_FIELDS, "event": EVENT_FIELDS}
CONFIDENCE = ["high", "medium", "low"]
DECISIONS = ["undecided", "keep", "take", "edit"]
DECIDED_EVENT = ("accepted", "rejected", "merged")
SEP = " | "

# the Re-review table: internal name -> label in the base (the connector's field ids are in airtable.json)
COLUMNS = {
    "finding": "Finding", "kind": "Kind", "record": "Record", "claimant": "Claimant", "year": "Year",
    "field": "Field", "current": "Current", "proposed": "Proposed", "reasoning": "Reasoning",
    "evidence": "Evidence", "chubb": "Chubb comparison", "confidence": "Confidence", "audit": "Audit",
    "decision": "Decision", "your_value": "Your value", "your_note": "Your note",
}


LABEL_TO_COLUMN = {v: k for k, v in COLUMNS.items()}


class FindingError(ValueError):
    pass


def normalise_record(r: dict, field_ids: dict[str, str] | None = None) -> dict:
    """One Re-review row keyed by internal name with plain values, whatever the export shape (fields by
    id, by label or by internal name)."""
    names = {v: k for k, v in (field_ids or {}).items()}
    raw = r["cellValuesByFieldId"] if "cellValuesByFieldId" in r else r.get("fields", r)
    return {names.get(k) or LABEL_TO_COLUMN.get(k, k): _plain(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# rendering a record's field as the one string a finding compares, and reading one back

def _flags(row: dict, names: list[str]) -> str:
    return ", ".join(n for n in names if row.get(n) == "1")


def _subs(row: dict) -> str:
    return ", ".join(str(i + 1) for i, n in enumerate(schema.SUBREGION_FLAGS) if row.get(n) == "1")


def render(kind: str, row: dict, field: str) -> str:
    """The record's current value of `field`, written as findings write it."""
    if kind == "move":
        if field == "type":
            return _flags(row, schema.TYPE_FLAGS)
        if field == "domains":
            return _flags(row, schema.DOMAIN_FLAGS)
        if field == "issues":
            return _flags(row, schema.ISSUE_FLAGS)
        if field == "subregions":
            return _subs(row)
        if field == "withdraw":
            return row.get("status", "")
        return row.get(field, "")
    if field == "decision":
        return row.get("status", "")
    if field == "move":
        return row.get("move_id", "")
    if field == "date":
        return SEP.join([row.get("date_start", ""), row.get("date_end", ""), row.get("date_precision", "")])
    if field == "place":
        return SEP.join(row.get(c, "") for c in ("location_name", "lat", "lon", "location_precision", "subregion"))
    return row.get(field, "")


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _split_list(value: str, allowed: list[str], what: str) -> list[str]:
    items = [x.strip().lower() for x in re.split(r"[,;]", value or "") if x.strip()]
    bad = [x for x in items if x not in allowed]
    if bad:
        raise FindingError(f"unknown {what}: {', '.join(bad)} (allowed: {', '.join(allowed)})")
    return [n for n in allowed if n in items]          # schema order, no repeats


def _parts(value: str, n: int, what: str) -> list[str]:
    parts = [p.strip() for p in (value or "").split("|")]
    if len(parts) != n:
        raise FindingError(f"{what} needs {n} parts separated by ' | ', got {len(parts)}: {value!r}")
    return parts


def parse(kind: str, field: str, value: str, moves: dict[str, dict], row: dict) -> dict:
    """The column changes that writing `value` into `field` means, checked; raises FindingError."""
    v = _norm(value)
    if kind == "move":
        if field == "type":
            if v.lower() not in schema.TYPE_FLAGS:
                raise FindingError(f"type must be one of {', '.join(schema.TYPE_FLAGS)}, got {v!r}")
            return {n: "1" if n == v.lower() else "0" for n in schema.TYPE_FLAGS}
        if field in ("domains", "issues"):
            names = schema.DOMAIN_FLAGS if field == "domains" else schema.ISSUE_FLAGS
            got = _split_list(v, names, field)
            if not got:
                raise FindingError(f"a move needs at least one of the {field}")
            return {n: "1" if n in got else "0" for n in names}
        if field == "subregions":
            nums = [x.strip() for x in re.split(r"[,;]", v) if x.strip()]
            if not nums or any(x not in {str(i) for i in range(1, 11)} for x in nums):
                raise FindingError(f"subregions must be numbers 1-10, comma-separated, got {v!r}")
            return {n: "1" if str(i + 1) in nums else "0" for i, n in enumerate(schema.SUBREGION_FLAGS)}
        if field == "dyads":
            pairs = v.upper().split()
            if not pairs or any(len(x) not in (1, 2) or set(x) - schema.DYAD_LETTERS for x in pairs):
                raise FindingError(f"dyads must be letter pairs from {''.join(sorted(schema.DYAD_LETTERS))}, space-separated, got {v!r}")
            return {"dyads": " ".join(pairs)}
        if field == "intensification_criterion":
            if v not in schema.INTENSIFICATION_CRITERIA:
                raise FindingError(f"intensification_criterion must be one of {', '.join(schema.INTENSIFICATION_CRITERIA)}")
            return {"intensification_criterion": v}
        if field == "ongoing_through":
            if not re.fullmatch(r"\d{4}", v) or int(v) < int(row.get("year") or 0):
                raise FindingError(f"ongoing_through must be a year no earlier than the move's ({row.get('year')}), got {v!r}")
            return {"ongoing_through": v}
        if field == "description":
            if not v:
                raise FindingError("an empty description")
            return {"description": v}
        if field == "withdraw":
            if v.lower() != "withdraw":
                raise FindingError("the only proposal for withdraw is 'withdraw'")
            return {"__withdraw__": "1"}
    else:
        if field == "decision":
            low = v.lower()
            if low == "reject":
                return {"status": "rejected", "move_id": ""}
            if low == "reconsider":
                return {"status": "candidate", "move_id": ""}
            m = re.fullmatch(r"accept into (\S+)", v, flags=re.I)
            if m:
                mid = m.group(1)
                if mid not in moves:
                    raise FindingError(f"no move {mid}")
                return {"status": "accepted", "move_id": mid}
            raise FindingError("decision must be 'reject', 'reconsider' or 'accept into MOVE_ID'")
        if field == "move":
            if v not in moves:
                raise FindingError(f"no move {v!r}")
            return {"move_id": v}
        if field == "date":
            start, end, prec = _parts(v, 3, "date")
            for d in (start, end):
                if d and not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", d):
                    raise FindingError(f"not a date: {d!r}")
            if not start:
                raise FindingError("a date needs date_start")
            if prec not in schema.DATE_PRECISION:
                raise FindingError(f"date_precision must be one of {', '.join(schema.DATE_PRECISION)}")
            return {"date_start": start, "date_end": end, "date_precision": prec}
        if field == "place":
            name, lat, lon, prec, sub = _parts(v, 5, "place")
            for c in (lat, lon):
                if c:
                    try:
                        float(c)
                    except ValueError:
                        raise FindingError(f"not a coordinate: {c!r}") from None
            if bool(lat) != bool(lon):
                raise FindingError("a place needs both coordinates or neither")
            if prec not in schema.LOCATION_PRECISION:
                raise FindingError(f"location_precision must be one of {', '.join(schema.LOCATION_PRECISION)}")
            if sub and sub not in {str(i) for i in range(1, 11)}:
                raise FindingError(f"subregion must be 1-10 or empty, got {sub!r}")
            return {"location_name": name, "lat": lat, "lon": lon, "location_precision": prec, "subregion": sub}
        if field == "summary":
            if not v:
                raise FindingError("an empty summary")
            return {"summary": v}
    raise FindingError(f"{kind} field {field!r} is not one a finding may address")


# ---------------------------------------------------------------------------
# findings -> Airtable rows

def _records(data_dir: Path) -> tuple[dict, dict]:
    moves = {m["move_id"]: m for m in read_table("moves", data_dir)}
    events = {e["event_id"]: e for e in read_table("events", data_dir)}
    return moves, events


def eligible(kind: str, rid: str, moves: dict, events: dict) -> dict:
    """The record a finding addresses, if the audit may address it; raises FindingError otherwise."""
    if kind == "move":
        m = moves.get(rid)
        if not m:
            raise FindingError(f"no move {rid}")
        if m.get("coded_by") != "project":
            raise FindingError(f"{rid} is Chubb's (MATS): the benchmark, never re-coded here (ADR 0001)")
        return m
    if kind == "event":
        e = events.get(rid)
        if not e:
            raise FindingError(f"no event {rid}")
        if not e.get("extractor") or e.get("status") not in DECIDED_EVENT:
            raise FindingError(f"{rid} is not a harvested event the maintainer decided (status {e.get('status')!r})")
        return e
    raise FindingError(f"kind must be 'move' or 'event', got {kind!r}")


def check_finding(f: dict, moves: dict, events: dict) -> dict:
    """One finding, checked against the data; returns it normalised. Raises FindingError."""
    kind, rid, field = (f.get("kind") or "").strip(), (f.get("id") or "").strip(), (f.get("field") or "").strip()
    row = eligible(kind, rid, moves, events)
    if field not in FIELDS[kind]:
        raise FindingError(f"{kind} field {field!r} is not one of {', '.join(FIELDS[kind])}")
    now = render(kind, row, field)
    if _norm(f.get("current")) != _norm(now):
        raise FindingError(f"{rid} {field}: the finding says the current value is {f.get('current')!r}, the data says {now!r}")
    parse(kind, field, f.get("proposed", ""), moves, row)
    if _norm(f.get("proposed")) == _norm(now):
        raise FindingError(f"{rid} {field}: the proposal repeats the current value")
    if not _norm(f.get("reasoning")):
        raise FindingError(f"{rid} {field}: no reasoning")
    conf = (f.get("confidence") or "").strip().lower()
    if conf not in CONFIDENCE:
        raise FindingError(f"{rid} {field}: confidence must be one of {', '.join(CONFIDENCE)}")
    year = row.get("year") or (row.get("date_start") or "")[:4]
    return {"kind": kind, "id": rid, "field": field, "current": now, "proposed": _norm(f["proposed"]),
            "reasoning": f["reasoning"].strip(), "evidence": (f.get("evidence") or "").strip(),
            "chubb": (f.get("chubb") or "").strip(), "confidence": conf,
            "claimant": row.get("claimant", ""), "year": year}


def finding_id(audit: str, f: dict) -> str:
    return f"{audit}:{f['id']}:{f['field']}"


def rows_for_findings(findings: list[dict], audit: str, data_dir: Path, field_ids: dict[str, str],
                      batch: int = 10, max_bytes: int = 26000) -> tuple[list[list[dict]], list[str]]:
    """Airtable records for the findings, in batches; and the list of findings refused, with why.
    Two findings on one record's field are refused both: the maintainer answers one question at a time."""
    moves, events = _records(data_dir)
    ok, errors = [], []
    seen: dict[tuple, int] = {}
    for i, f in enumerate(findings):
        try:
            c = check_finding(f, moves, events)
        except FindingError as e:
            errors.append(f"finding {i + 1}: {e}")
            continue
        key = (c["kind"], c["id"], c["field"])
        if key in seen:
            errors.append(f"finding {i + 1}: a second finding on {c['id']} {c['field']} (the first is finding {seen[key] + 1}); merge them")
            ok = [x for x in ok if (x["kind"], x["id"], x["field"]) != key]
            continue
        seen[key] = i
        ok.append(c)
    missing = [n for n in COLUMNS if n not in field_ids]
    if missing:
        raise RuntimeError(f"pipeline/airtable.json rereview.field_ids lacks {', '.join(missing)}")
    out, cur, size = [], [], 2
    for c in ok:
        vals = {"finding": finding_id(audit, c), "kind": c["kind"], "record": c["id"], "claimant": c["claimant"],
                "year": c["year"], "field": c["field"], "current": c["current"], "proposed": c["proposed"],
                "reasoning": c["reasoning"], "evidence": c["evidence"], "chubb": c["chubb"],
                "confidence": c["confidence"], "audit": audit, "decision": "undecided"}
        one = {"fields": {field_ids[k]: v for k, v in vals.items() if v not in ("", None)}}
        n = len(json.dumps(one, ensure_ascii=False).encode()) + 1
        if cur and (len(cur) == batch or size + n > max_bytes):
            out.append(cur)
            cur, size = [], 2
        cur.append(one)
        size += n
    if cur:
        out.append(cur)
    return out, errors


# ---------------------------------------------------------------------------
# the maintainer's answers -> data

def _note(e: dict, text: str) -> None:
    e["review_note"] = (e.get("review_note", "").rstrip() + " " + text).strip()


def apply_decisions(exported: list[dict], data_dir: Path, today: str, field_ids: dict[str, str],
                    reviewer: str = "") -> dict:
    """Apply the decided rows of a Re-review export to data/. Returns a report:
    {"applied": [...], "kept": [...], "skipped": [...], "clear": [airtable ids], "undecided": n}.
    A row is skipped (and stays in the base) when its record changed since the finding was made, when its
    value does not parse, or when rejecting an event would leave its move without events (take the move's
    withdraw finding for that). Kept and applied rows are cleared."""
    moves_l, events_l = read_table("moves", data_dir), read_table("events", data_dir)
    moves = {m["move_id"]: m for m in moves_l}
    events = {e["event_id"]: e for e in events_l}
    report = {"applied": [], "kept": [], "skipped": [], "clear": [], "undecided": 0}
    rows = [(r.get("id", ""), normalise_record(r, field_ids)) for r in exported]
    # withdrawals first, so that a move withdrawn in this sitting may lose its events
    order = sorted(rows, key=lambda x: (x[1].get("field") != "withdraw",))
    withdrawn: set[str] = set()
    for rec_id, r in order:
        dec = (r.get("decision") or "undecided").strip().lower()
        label = f"{r.get('record', '?')} {r.get('field', '?')}"
        if dec == "undecided" or not dec:
            report["undecided"] += 1
            continue
        if dec not in DECISIONS:
            report["skipped"].append(f"{label}: unknown decision {dec!r}")
            continue
        note = _norm(r.get("your_note"))
        if dec == "keep":
            report["kept"].append(f"{label}: kept {r.get('current', '')!r}" + (f" ({note})" if note else ""))
            report["clear"].append(rec_id)
            continue
        value = r.get("proposed", "") if dec == "take" else r.get("your_value", "")
        if dec == "edit" and not _norm(value):
            report["skipped"].append(f"{label}: decided 'edit' without a value in Your value")
            continue
        kind, rid, field = r.get("kind", ""), r.get("record", ""), r.get("field", "")
        try:
            row = eligible(kind, rid, moves, events)
            if field not in FIELDS.get(kind, []):
                raise FindingError(f"field {field!r} is not one a finding may address")
            now = render(kind, row, field)
            if _norm(now) != _norm(r.get("current")):
                raise FindingError(f"changed since the finding: it was {r.get('current')!r}, it is now {now!r}")
            change = parse(kind, field, value, moves, row)
        except FindingError as e:
            report["skipped"].append(f"{label}: {e}")
            continue
        old = now
        if kind == "move" and "__withdraw__" in change:
            for e in events_l:
                if e["move_id"] == rid and e["status"] == "accepted":
                    e["status"], e["move_id"] = "rejected", ""
                    _note(e, f"[re-review {today}: rejected with its move {rid}, withdrawn. {note}]".replace(". ]", "]"))
            moves_l = [m for m in moves_l if m["move_id"] != rid]
            moves.pop(rid, None)
            withdrawn.add(rid)
        elif kind == "event" and field == "decision" and row["status"] == "accepted" and change["status"] != "accepted":
            mid = row["move_id"]
            left = [e for e in events_l if e["move_id"] == mid and e["status"] == "accepted" and e["event_id"] != rid]
            if mid and not left and mid not in withdrawn:
                report["skipped"].append(f"{label}: it is the last event of {mid}; decide that move's withdraw finding instead")
                continue
            row.update(change)
        else:
            row.update(change)
        if kind == "event":
            row["reviewer"] = reviewer or row.get("reviewer", "")
            _note(row, f"[re-review {today}: {field} {old!r} -> {_norm(value)!r}" + (f"; {note}" if note else "") + "]")
        report["applied"].append(f"{label}: {old!r} -> {_norm(value)!r} ({dec})")
        report["clear"].append(rec_id)
    write_table("moves", moves_l, data_dir)
    write_table("events", events_l, data_dir)
    return report


def archive(exported: list[dict], report: dict, out_dir: Path, today: str, field_ids: dict[str, str]) -> None:
    """File the sitting: records.json (every row as exported, accumulated by finding), applied-DATE.json
    (the report) and clear.json (the Airtable ids of the rows decided and applied or kept)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rec_path = out_dir / "records.json"
    kept: dict[str, dict] = {}
    if rec_path.exists():
        kept = {x["finding"]: x for x in json.loads(rec_path.read_text(encoding="utf-8")).get("records", [])}
    for r in exported:
        f = normalise_record(r, field_ids)
        if f.get("finding"):
            kept[f["finding"]] = {"airtable_id": r.get("id", ""), "archived_on": today,
                                  **{k: v for k, v in f.items() if v not in (None, "", [])}}
    rec_path.write_text(json.dumps({"records": sorted(kept.values(), key=lambda x: x["finding"])}, indent=1,
                                   ensure_ascii=False), encoding="utf-8")
    (out_dir / f"applied-{today}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / "clear.json").write_text(json.dumps({"table": "Re-review", "record_ids": report["clear"]}, indent=1),
                                        encoding="utf-8")


def config() -> dict:
    c = load_config().get("rereview") or {}
    return {"table_id": c.get("table_id", ""), "field_ids": c.get("field_ids") or {}}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rows", help="check findings and write the Re-review rows in batches")
    r.add_argument("--findings", type=Path, required=True)
    r.add_argument("--audit", required=True, help="the audit's id, e.g. AUDIT-20261201")
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--data", type=Path, default=Path("data"))
    r.add_argument("--batch", type=int, default=10)
    a_ = sub.add_parser("apply", help="apply the decided rows of a Re-review export")
    a_.add_argument("--from", dest="from_file", type=Path, required=True)
    a_.add_argument("--date", default="")
    a_.add_argument("--data", type=Path, default=Path("data"))
    a_.add_argument("--out-dir", type=Path, default=Path("harvest/airtable/rereview"))
    a_.add_argument("--reviewer", default=None)
    a = p.parse_args(argv)
    ids = config()["field_ids"]
    if a.cmd == "rows":
        findings = json.loads(a.findings.read_text(encoding="utf-8"))
        findings = findings.get("findings", findings) if isinstance(findings, dict) else findings
        batches, errors = rows_for_findings(findings, a.audit, a.data, ids, a.batch)
        a.out.write_text(json.dumps(batches, indent=1, ensure_ascii=False), encoding="utf-8")
        n = sum(len(b) for b in batches)
        print(f"{n} row(s) in {len(batches)} batch(es) -> {a.out}; {len(errors)} finding(s) refused")
        for e in errors:
            print("  refused:", e)
        return 0 if n or not errors else 1
    today = a.date or dt.date.today().isoformat()
    exported = json.loads(a.from_file.read_text(encoding="utf-8"))
    exported = exported.get("records", exported) if isinstance(exported, dict) else exported
    reviewer = a.reviewer if a.reviewer is not None else (load_config().get("reviewer") or "")
    report = apply_decisions(exported, a.data, today, ids, reviewer)
    archive(exported, report, a.out_dir, today, ids)
    print(f"applied {len(report['applied'])}, kept {len(report['kept'])}, skipped {len(report['skipped'])}, "
          f"undecided {report['undecided']}; {len(report['clear'])} row(s) to clear -> {a.out_dir / 'clear.json'}")
    for s in report["skipped"]:
        print("  skipped:", s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
