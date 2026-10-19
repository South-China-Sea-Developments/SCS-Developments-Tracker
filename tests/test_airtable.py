"""Seam 1 through Airtable (ticket 13): the fixture run decided in a (fake) Airtable table yields
exactly the files that the same decisions yield through the review page's JSON export; the sync is
idempotent, counts its calls, can be switched off, and nothing that builds the dataset or the site
imports it (ADR 0004: files in the repository are canonical)."""
from __future__ import annotations

import ast
import csv
import filecmp
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pipeline import airtable, harvest, queue
from tests.conftest import DATA_DIR, RAW_MAVD, RAW_XLSX, ROOT

FIX = ROOT / "tests/fixtures/harvest"
REVIEWER, DATE = "Test Coder", "2026-10-15"


class FakeAirtable(airtable.Client):
    """The same interface, backed by a dict, with the same call counting and batching rules."""

    def __init__(self, max_calls: int = 200):
        super().__init__("fake-token", "appFAKE", "Candidates", max_calls)
        self.rows: dict[str, dict] = {}
        self.n = 0

    def _request(self, method, path="", params=None, body=None):
        self._check()
        self.calls += 1
        if method == "GET":
            formula = (params or {}).get("filterByFormula", "")
            run = formula.split("'")[1] if "'" in formula else None
            recs = [{"id": i, "fields": dict(f)} for i, f in self.rows.items() if run is None or f.get("run_id") == run]
            return {"records": recs}
        if method == "POST":
            out = []
            for r in body["records"]:
                self.n += 1
                rid = f"rec{self.n:05d}"
                self.rows[rid] = dict(r["fields"])
                out.append({"id": rid, "fields": dict(r["fields"])})
            return {"records": out}
        if method == "PATCH":
            for r in body["records"]:
                self.rows[r["id"]].update(r["fields"])
            return {"records": []}
        if method == "DELETE":
            for rid in params["records[]"]:
                self.rows.pop(rid)
            return {"records": []}
        raise AssertionError(method)

    def decide(self, event_id: str, **coder_fields):
        """What the coder does in the Airtable grid: fill the decision columns of one row."""
        rid = next(i for i, f in self.rows.items() if f["event_id"] == event_id)
        self.rows[rid].update(coder_fields)


def opened_copy(tmp_path: Path, name: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    for f in ("claimants", "moves", "events", "sources", "corrections"):
        shutil.copy(DATA_DIR / f"{f}.csv", d / f"{f}.csv")
    run = tmp_path / f"run-{name}"
    assert harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(run),
                         "--recordings", str(FIX / "recordings"), "--run-id", "fixture"]) == 0
    assert queue.append_run(run, d)[0] == 5
    return d


def candidates(d: Path) -> dict[str, dict]:
    with open(d / "events.csv", newline="", encoding="utf-8") as f:
        return {r["location_name"] or "headline": r for r in csv.DictReader(f) if r["status"] == "candidate" and r["harvest_run_id"] == "fixture"}


def test_same_decisions_through_airtable_and_through_the_review_page_yield_identical_files(tmp_path):
    a, b = opened_copy(tmp_path, "airtable"), opened_copy(tmp_path, "page")
    assert filecmp.cmp(a / "events.csv", b / "events.csv", shallow=False)
    cands = candidates(a)
    pick = lambda prefix: next(x for x in cands.values() if x["location_name"].startswith(prefix))
    stas, scar, thitu, headline = pick("Second"), pick("Scarb"), pick("Thitu"), cands["headline"]
    vn = next(x for x in cands.values() if x["claimant"] == "VN")

    # the review page's export for these five candidates (the shape tests/test_queue.py checks)
    page_decisions = {"reviewer": REVIEWER, "decisions": [
        {"event_id": scar["event_id"], "action": "new_move", "note": "First physical interference at Scarborough this year.",
         "new_move": {"type": "coercive", "intensification_criterion": "frequency", "year": "", "ongoing_through": "2026", "dyads": ["CP"],
                      "domains": ["physical"], "issues": ["military", "administrative"], "subregions": ["4"],
                      "description": "2026, October 4: CCG and PLA units interfere with Philippine aircraft and vessels near Scarborough Shoal."}},
        {"event_id": thitu["event_id"], "action": "merge", "note": "Same operation, second area.", "move_of_event": scar["event_id"],
         "edits": {"subregion": "5", "summary": "Same-day interference near Thitu Island and Sandy Cay."}},
        {"event_id": stas["event_id"], "action": "new_move", "note": "",
         "new_move": {"type": "coercive", "intensification_criterion": "novelty", "year": "", "ongoing_through": "", "dyads": ["CP"],
                      "domains": ["physical"], "issues": ["military"], "subregions": ["6"], "description": ""}},
        {"event_id": headline["event_id"], "action": "reject", "note": "Headline only; incident location unknown."},
        {"event_id": vn["event_id"], "action": "new_move", "note": "",
         "new_move": {"type": "declarative", "intensification_criterion": "novelty", "year": "2026", "ongoing_through": "", "dyads": ["VC"],
                      "domains": ["diplomatic"], "issues": ["politics"], "subregions": ["2"], "description": ""}},
    ]}

    # the same five decisions made in the Airtable grid
    fake = FakeAirtable()
    res = airtable.push(fake, airtable.records_for_run(a, "fixture", pr=17), "fixture")
    assert res["created"] == 5 and res["updated"] == 0 and res["calls"] == 2        # one list, one batch of five
    fake.decide(scar["event_id"], decision="new_move", note="First physical interference at Scarborough this year.", new_type="coercive",
                new_criterion="frequency", new_ongoing_through="2026", new_dyads="CP", new_domains=["physical"], new_issues=["military", "administrative"],
                new_subregions=[airtable.SUBREGION_CHOICES[3]],
                new_description="2026, October 4: CCG and PLA units interfere with Philippine aircraft and vessels near Scarborough Shoal.")
    fake.decide(thitu["event_id"], decision="merge", note="Same operation, second area.", merge_into_candidate=scar["event_id"],
                edit_subregion=airtable.SUBREGION_CHOICES[4], edit_summary="Same-day interference near Thitu Island and Sandy Cay.")
    fake.decide(stas["event_id"], decision="new_move", new_type="coercive", new_criterion="novelty", new_dyads="CP", new_domains=["physical"],
                new_issues=["military"], new_subregions=[airtable.SUBREGION_CHOICES[5]], reviewer=REVIEWER)
    fake.decide(headline["event_id"], decision="reject", note="Headline only; incident location unknown.")
    fake.decide(vn["event_id"], decision="new_move", new_type="declarative", new_criterion="novelty", new_year="2026", new_dyads="VC",
                new_domains=["diplomatic"], new_issues=["politics"], new_subregions=[airtable.SUBREGION_CHOICES[1]])
    pulled = airtable.pull(fake, "fixture")
    page_decisions["decisions"].sort(key=lambda d: d["event_id"])
    assert pulled == page_decisions                                                   # byte-for-byte the page's export

    ca = queue.apply_decisions(pulled["decisions"], pulled["reviewer"], DATE, a, RAW_XLSX, RAW_MAVD)
    cb = queue.apply_decisions(page_decisions["decisions"], page_decisions["reviewer"], DATE, b, RAW_XLSX, RAW_MAVD)
    assert ca == cb == {"rejected": 1, "merged": 1, "new_moves": 3, "duplicates": 0, "accepted_events": 4}
    for f in ("claimants", "moves", "events", "sources", "corrections"):
        assert filecmp.cmp(a / f"{f}.csv", b / f"{f}.csv", shallow=False), f

    # once decided, the run's records can go; the base stays small
    assert airtable.clear(fake, "fixture") == 5 and fake.rows == {}


def test_push_is_idempotent_and_never_touches_the_coders_columns(tmp_path):
    d = opened_copy(tmp_path, "d")
    fake = FakeAirtable()
    recs = airtable.records_for_run(d, "fixture", pr=17)
    airtable.push(fake, recs, "fixture")
    eid = recs[0]["event_id"]
    fake.decide(eid, decision="reject", note="keep me")
    res = airtable.push(fake, recs, "fixture")
    assert res["created"] == 0 and res["updated"] == 5
    row = next(f for f in fake.rows.values() if f["event_id"] == eid)
    assert row["decision"] == "reject" and row["note"] == "keep me" and row["pull_request"] == 17
    assert len(fake.rows) == 5
    # context the coder needs is there, as on the page
    assert all(r["sources"] and r["summary"] and r["claimant"] for r in recs)
    assert any(r.get("possible_duplicate_of") for r in recs)            # the fixture run has one flagged duplicate


def test_undecided_rows_and_blank_edits_are_skipped():
    recs = [{"fields": {"event_id": "e1", "run_id": "r", "decision": "undecided", "note": "thinking"}},
            {"fields": {"event_id": "e2", "run_id": "r", "decision": "reject", "note": "no", "edit_summary": "", "edit_lat": None}},
            {"fields": {"event_id": "e3", "run_id": "r", "decision": "merge", "merge_into_move": "CN201501 ", "edit_lat": 10.5, "edit_subregion": airtable.SUBREGION_CHOICES[0]}}]
    d = airtable.decisions_from_records(recs, reviewer="R")
    assert [x["event_id"] for x in d["decisions"]] == ["e2", "e3"]
    assert d["decisions"][0] == {"event_id": "e2", "action": "reject", "note": "no"}
    assert d["decisions"][1] == {"event_id": "e3", "action": "merge", "note": "", "move_id": "CN201501", "edits": {"lat": "10.5", "subregion": "1"}}
    assert d["reviewer"] == "R"
    # two different reviewer names in the rows and none given: the file names nobody and `queue decide` asks
    recs[1]["fields"]["reviewer"], recs[2]["fields"]["reviewer"] = "A", "B"
    assert "reviewer" not in airtable.decisions_from_records(recs)


def test_records_exported_by_another_client_pull_the_same_decisions():
    """Select values as {id, name} objects and fields keyed by id (as the Airtable MCP connector
    returns them) give the same decisions as the REST shape."""
    ids = {"event_id": "fld1", "run_id": "fld2", "decision": "fld3", "note": "fld4", "merge_into_move": "fld5", "edit_subregion": "fld6", "new_domains": "fld7", "new_type": "fld8", "new_criterion": "fld9"}
    rest = [{"fields": {"event_id": "e1", "run_id": "r", "decision": "merge", "note": "n", "merge_into_move": "CN201501", "edit_subregion": airtable.SUBREGION_CHOICES[2]}},
            {"fields": {"event_id": "e2", "run_id": "r", "decision": "new_move", "note": "", "new_type": "coercive", "new_criterion": "scope", "new_domains": ["physical", "diplomatic"]}}]
    other = [{"id": "recA", "cellValuesByFieldId": {"fld1": "e1", "fld2": "r", "fld3": {"id": "selX", "name": "merge", "color": "blueLight2"}, "fld4": "n", "fld5": "CN201501",
                                                    "fld6": {"id": "selY", "name": airtable.SUBREGION_CHOICES[2], "color": "grayLight2"}}},
             {"id": "recB", "cellValuesByFieldId": {"fld1": "e2", "fld2": "r", "fld3": {"id": "selZ", "name": "new_move"}, "fld8": {"name": "coercive"}, "fld9": {"name": "scope"},
                                                    "fld7": [{"name": "physical"}, {"name": "diplomatic"}]}}]
    assert airtable.decisions_from_records(other, "R", ids) == airtable.decisions_from_records(rest, "R")
    assert airtable.decisions_from_records(rest, "R")["decisions"][1]["new_move"]["domains"] == ["physical", "diplomatic"]


def test_the_call_budget_stops_before_the_request():
    fake = FakeAirtable(max_calls=2)
    airtable.push(fake, [{"event_id": f"e{i}", "run_id": "r"} for i in range(5)], "r")      # list + one batch = 2
    with pytest.raises(RuntimeError, match="max-calls"):
        airtable.push(fake, [{"event_id": "e9", "run_id": "r"}], "r")
    assert fake.calls == 2 and len(fake.rows) == 5


def test_disabled_configuration_does_nothing(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "airtable.json"
    monkeypatch.setattr(airtable, "CONFIG", cfg)
    monkeypatch.delenv("AIRTABLE_TOKEN", raising=False)
    monkeypatch.setattr(airtable.Client, "_request", lambda *a, **k: pytest.fail("Airtable was called"))
    assert airtable.main(["push", "--run", "fixture"]) == 0
    assert "disabled" in capsys.readouterr().out
    cfg.write_text(json.dumps({"enabled": True, "base_id": "appX", "table": "Candidates"}))
    assert airtable.main(["clear", "--run", "fixture"]) == 0
    assert "AIRTABLE_TOKEN is not set" in capsys.readouterr().out


def test_offline_routes_need_no_token(tmp_path, monkeypatch):
    d = opened_copy(tmp_path, "d")
    out = tmp_path / "records.json"
    assert airtable.main(["records", "--run", "fixture", "--data", str(d), "--out", str(out)]) == 0
    recs = json.loads(out.read_text(encoding="utf-8"))
    assert len(recs) == 5 and all(r["decision"] == "undecided" for r in recs)
    recs[0].update(decision="reject", note="n")
    out.write_text(json.dumps(recs), encoding="utf-8")
    dec = tmp_path / "decisions.json"
    assert airtable.main(["pull", "--run", "fixture", "--from", str(out), "--out", str(dec), "--reviewer", "R"]) == 0
    assert json.loads(dec.read_text(encoding="utf-8")) == {"reviewer": "R", "decisions": [{"event_id": recs[0]["event_id"], "action": "reject", "note": "n"}]}


def test_schema_matches_what_the_review_page_offers():
    s = airtable.table_schema()
    names = [f["name"] for f in s["fields"]]
    for col in queue.EDITABLE:
        if col != "location_precision":
            assert f"edit_{col}" in names, col
    # the live base recorded in the configuration has every field the code writes or reads
    cfg = json.loads((ROOT / "pipeline" / "airtable.json").read_text(encoding="utf-8"))
    assert set(cfg["field_ids"]) == set(names)
    dec = next(f for f in s["fields"] if f["name"] == "decision")
    assert [c["name"] for c in dec["options"]["choices"]] == ["undecided", "merge", "new_move", "duplicate", "reject"]


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out |= {n.module} | {f"{n.module}.{a.name}" for a in n.names}
    return out


def test_nothing_that_builds_the_dataset_or_the_site_knows_airtable_exists():
    for p in [ROOT / "pipeline" / f for f in ("load_mats.py", "validate.py", "queue.py", "harvest.py", "release.py", "agreement.py", "gazetteer.py")] \
            + list((ROOT / "web").glob("*.py")):
        assert not any("airtable" in i for i in imports_of(p)), p
    # and a clean subprocess that loads, validates and builds never imports the module
    code = "import sys; from pipeline import validate, queue, load_mats; import web.build; print('pipeline.airtable' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip() == "False"
