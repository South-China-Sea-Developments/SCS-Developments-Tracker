"""Ticket 43: findings become Re-review rows; the maintainer's answers are applied to the data."""
import collections
import csv
import shutil

import pytest

from pipeline import rereview, validate
from tests.conftest import DATA_DIR, ROOT

IDS = {k: f"fld{k[:10]:_<10}xxxx"[:17] for k in rereview.COLUMNS}      # stand-in field ids


def table(d, name):
    with open(d / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    shutil.copytree(DATA_DIR, d, ignore=shutil.ignore_patterns("raw"))
    return d


def picks(d):
    """A project move with two accepted events, one with a single accepted event, a Chubb move, and a
    rejected harvested event, from the live data."""
    moves = {m["move_id"]: m for m in table(d, "moves")}
    events = table(d, "events")
    n = collections.Counter(e["move_id"] for e in events if e["status"] == "accepted")
    proj = [m for m in moves.values() if m["coded_by"] == "project"]
    two = next(m for m in proj if n[m["move_id"]] >= 2)
    one = next(m for m in proj if n[m["move_id"]] == 1)
    chubb = next(m for m in moves.values() if m["coded_by"] == "chubb")
    rejected = next(e for e in events if e["status"] == "rejected" and e["extractor"])
    last = next(e for e in events if e["move_id"] == one["move_id"] and e["status"] == "accepted")
    return two, one, chubb, rejected, last


def other_type(m):
    return next(t for t in ("declarative", "demonstrative", "coercive", "force") if m[t] != "1")


def finding(kind, rid, field, current, proposed, **kw):
    return {"kind": kind, "id": rid, "field": field, "current": current, "proposed": proposed,
            "reasoning": kw.get("reasoning", "because"), "confidence": kw.get("confidence", "high"),
            "evidence": kw.get("evidence", ""), "chubb": kw.get("chubb", "")}


def exported(batches, decisions):
    """The rows as the connector would export them, with the maintainer's answers filled in."""
    recs = []
    for i, f in enumerate(r for b in batches for r in b):
        fields = dict(f["fields"])
        key = (fields[IDS["record"]], fields[IDS["field"]])
        dec = decisions.get(key, ("undecided", "", ""))
        fields[IDS["decision"]] = {"id": "selx", "name": dec[0]}
        if dec[1]:
            fields[IDS["your_value"]] = dec[1]
        if dec[2]:
            fields[IDS["your_note"]] = dec[2]
        recs.append({"id": f"rec{i:014d}", "cellValuesByFieldId": fields})
    return recs


def test_render_and_parse_agree_on_every_field(data):
    two, *_ = picks(data)
    moves = {m["move_id"]: m for m in table(data, "moves")}
    for field in rereview.MOVE_FIELDS:
        if field in ("withdraw",):
            continue
        now = rereview.render("move", two, field)
        change = rereview.parse("move", field, now, moves, two)
        assert all(two.get(k) == v for k, v in change.items()), field


def test_rows_refuse_what_the_audit_may_not_change(data):
    two, one, chubb, rejected, last = picks(data)
    t = rereview.render("move", two, "type")
    findings = [
        finding("move", two["move_id"], "type", t, other_type(two)),                       # fine
        finding("move", chubb["move_id"], "type", rereview.render("move", chubb, "type"), "force"),  # Chubb's
        finding("move", one["move_id"], "type", "not what it is", "force"),                  # stale
        finding("move", one["move_id"], "type", rereview.render("move", one, "type"), "violent"),   # bad value
        finding("event", rejected["event_id"], "decision", "rejected", "accept into NOPE0000"),     # no such move
        finding("move", one["move_id"], "dyads", one["dyads"], one["dyads"]),                 # no change
    ]
    batches, errors = rereview.rows_for_findings(findings, "AUDIT-T", data, IDS)
    rows = [r for b in batches for r in b]
    assert len(rows) == 1 and rows[0]["fields"][IDS["finding"]] == f"AUDIT-T:{two['move_id']}:type"
    assert rows[0]["fields"][IDS["decision"]] == "undecided"
    assert len(errors) == 5
    assert any("Chubb" in e for e in errors) and any("data says" in e for e in errors)


def test_two_findings_on_one_field_are_both_refused(data):
    two, *_ = picks(data)
    t = rereview.render("move", two, "type")
    f = finding("move", two["move_id"], "type", t, other_type(two))
    batches, errors = rereview.rows_for_findings([f, dict(f, proposed="force" if other_type(two) != "force" else "declarative")],
                                                 "A", data, IDS)
    assert not [r for b in batches for r in b] and len(errors) == 1


def test_apply_takes_edits_keeps_and_skips(data):
    two, one, chubb, rejected, last = picks(data)
    new_type = other_type(two)
    findings = [
        finding("move", two["move_id"], "type", rereview.render("move", two, "type"), new_type),
        finding("move", two["move_id"], "subregions", rereview.render("move", two, "subregions"), "1, 2"),
        finding("event", rejected["event_id"], "decision", "rejected", f"accept into {two['move_id']}"),
        finding("event", last["event_id"], "decision", "accepted", "reject"),
        finding("move", one["move_id"], "dyads", one["dyads"], "CV"),
    ]
    batches, errors = rereview.rows_for_findings(findings, "A", data, IDS)
    assert not errors
    exp = exported(batches, {
        (two["move_id"], "type"): ("take", "", ""),
        (two["move_id"], "subregions"): ("edit", "2", "only the Paracels"),
        (rejected["event_id"], "decision"): ("keep", "", "my call stands"),
        (last["event_id"], "decision"): ("take", "", ""),                    # the move's last event: refused
    })
    rep = rereview.apply_decisions(exp, data, "2026-12-01", IDS, "Angelo")
    assert len(rep["applied"]) == 2 and len(rep["kept"]) == 1 and rep["undecided"] == 1
    assert len(rep["skipped"]) == 1 and "last event" in rep["skipped"][0]
    assert len(rep["clear"]) == 3
    m = {x["move_id"]: x for x in table(data, "moves")}[two["move_id"]]
    assert m[new_type] == "1" and sum(m[t] == "1" for t in ("declarative", "demonstrative", "coercive", "force")) == 1
    assert rereview.render("move", m, "subregions") == "2"
    e = {x["event_id"]: x for x in table(data, "events")}
    assert e[rejected["event_id"]]["status"] == "rejected"          # kept
    assert e[last["event_id"]]["status"] == "accepted"              # skipped


def test_apply_skips_a_row_whose_record_changed_since(data):
    two, *_ = picks(data)
    f = finding("move", two["move_id"], "dyads", two["dyads"], "CV")
    batches, _ = rereview.rows_for_findings([f], "A", data, IDS)
    moves = table(data, "moves")
    for m in moves:
        if m["move_id"] == two["move_id"]:
            m["dyads"] = "CP"
    rereview.write_table("moves", moves, data)
    rep = rereview.apply_decisions(exported(batches, {(two["move_id"], "dyads"): ("take", "", "")}), data, "2026-12-01", IDS)
    assert not rep["applied"] and "changed since" in rep["skipped"][0] and not rep["clear"]


def test_withdrawing_a_move_rejects_its_events_and_the_data_still_validates(data):
    _, one, _, _, last = picks(data)
    f = finding("move", one["move_id"], "withdraw", "accepted", "withdraw")
    batches, errors = rereview.rows_for_findings([f], "A", data, IDS)
    assert not errors
    rep = rereview.apply_decisions(exported(batches, {(one["move_id"], "withdraw"): ("take", "", "not a step up")}),
                                   data, "2026-12-01", IDS, "Angelo")
    assert len(rep["applied"]) == 1
    assert one["move_id"] not in {m["move_id"] for m in table(data, "moves")}
    e = {x["event_id"]: x for x in table(data, "events")}[last["event_id"]]
    assert e["status"] == "rejected" and "withdrawn" in e["review_note"] and e["move_id"] == ""
    errs = validate.validate(data, ROOT / "data/raw/mats-1.02/MATS_1-02_all_cases.xlsx",
                             ROOT / "data/raw/mavd-arcgis-2023/All_Actions7.csv")
    assert errs == [], errs[:5]


def test_archive_files_the_sitting(data, tmp_path):
    two, *_ = picks(data)
    batches, _ = rereview.rows_for_findings([finding("move", two["move_id"], "dyads", two["dyads"], "CV")], "A", data, IDS)
    exp = exported(batches, {(two["move_id"], "dyads"): ("keep", "", "")})
    rep = rereview.apply_decisions(exp, data, "2026-12-01", IDS)
    out = tmp_path / "arch"
    rereview.archive(exp, rep, out, "2026-12-01", IDS)
    import json
    assert json.loads((out / "clear.json").read_text())["record_ids"] == rep["clear"]
    recs = json.loads((out / "records.json").read_text())["records"]
    assert recs[0]["finding"] == f"A:{two['move_id']}:dyads" and recs[0]["decision"] == "keep"
    assert (out / "applied-2026-12-01.json").exists()
