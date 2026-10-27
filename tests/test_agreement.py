"""The agreement report: machine suggestions versus the coder's final coding, from a fixture whose
answer is known by hand; the site build regenerates it and the methodology page renders it."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from pipeline import agreement, schema
from tests.conftest import DATA_DIR

ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR_A, EXTRACTOR_B = "model-a@prompt-111111", "model-b@prompt-222222"


def move(mid, **flags):
    m = {c: "" for c in schema.TABLES["moves"]}
    m.update(move_id=mid, claimant=mid[:2], year=mid[2:6], instance_no=mid[6:], status="accepted", coded_by="project",
             coder="T", coding_date="2026-10-20", data_version="2.0.0-dev", dyads=flags.pop("dyads", "CP"),
             intensification_criterion="novelty", description="x", ongoing_through=mid[2:6])
    for f in schema.TYPE_FLAGS + schema.DOMAIN_FLAGS + schema.ISSUE_FLAGS + schema.SUBREGION_FLAGS:
        m[f] = "1" if flags.get(f) else "0"
    return m


def event(eid, mid, status, extractor, s_type, s_dom, s_iss, s_dyads, s_move="", year="2026", review_date="2026-10-20"):
    e = {c: "" for c in schema.TABLES["events"]}
    e.update(event_id=eid, move_id=mid, claimant=(mid or "CN")[:2], date_start=f"{year}-05-01", date_end=f"{year}-05-01", date_precision="day",
             summary="x", status=status, harvest_run_id="r", extractor=extractor, suggested_move_id=s_move, suggested_type=s_type,
             suggested_domains=s_dom, suggested_issues=s_iss, suggested_dyads=s_dyads, suggestion_reasoning="because",
             reviewer="T", review_date=review_date, review_note="n" if status == "rejected" else "")
    return e


@pytest.fixture
def fixture():
    moves = [
        move("CN202601", coercive=1, physical=1, military=1, administrative=1, loc04_central_east=1),
        move("CN202602", demonstrative=1, physical=1, energy=1, loc09_nam_con_son=1, dyads="CV"),
        move("VN202601", declarative=1, diplomatic=1, politics=1, dyads="VC"),
        move("CN202501", coercive=1, physical=1, fisheries=1),   # an older move an event was merged into
    ]
    events = [
        # extractor A, 2026: type right, domains right, issues partly wrong, dyads right; no move suggested (grouping not applicable)
        event("e1", "CN202601", "accepted", EXTRACTOR_A, "coercive", "physical", "military", "CP"),
        # extractor A, 2026: type wrong (said demonstrative), domains wrong, issues right, dyads right; suggested the existing move CN202501, coder chose CN202601
        event("e2", "CN202601", "accepted", EXTRACTOR_A, "demonstrative", "physical diplomatic", "military administrative", "CP", s_move="CN202501"),
        # extractor A, 2026: everything right incl. dyads CV; no move suggested
        event("e3", "CN202602", "accepted", EXTRACTOR_A, "demonstrative", "physical", "energy", "CV"),
        # extractor A, 2026: rejected by the coder (counts as an outcome, not a coding comparison)
        event("e4", "", "rejected", EXTRACTOR_A, "declarative", "diplomatic", "politics", "CP"),
        # extractor A, 2026: duplicate report (status merged): an outcome, not a coding comparison
        event("e5", "CN202601", "merged", EXTRACTOR_A, "coercive", "physical", "military", "CP"),
        # extractor B, 2026: type right; suggested the existing move VN202501, the coder formed VN202601 (grouping wrong)
        event("e6", "VN202601", "accepted", EXTRACTOR_B, "declarative", "diplomatic", "politics", "VC", s_move="VN202501"),
        # extractor B, 2025: suggested the older move CN202501 and the coder merged it there (grouping right); type right, dyads wrong
        event("e7", "CN202501", "accepted", EXTRACTOR_B, "coercive", "physical", "fisheries", "CV", s_move="CN202501", year="2025", review_date="2026-10-21"),
        # a candidate still waiting: not counted anywhere
        event("e8", "", "candidate", EXTRACTOR_B, "coercive", "physical", "military", "CP"),
        # a MATS-era seed event: no extractor, never counted
        event("e9", "CN202501", "accepted", "", "", "", "", ""),
        # extractor B, 2026: the extractor could not name a Type; rejected - still a decided suggestion
        event("e10", "", "rejected", EXTRACTOR_B, "", "physical", "military", "CP"),
        # extractor B, 2026: no Type named, accepted into CN202602: a Type disagreement, domains right
        event("e11", "CN202602", "accepted", EXTRACTOR_B, "", "physical", "energy", "CV"),
    ]
    return moves, events


def test_report_numbers_by_hand(fixture):
    moves, events = fixture
    r = agreement.report(events, moves)
    assert r["n_compared"] == 6 and r["n_decided"] == 9           # e1 e2 e3 e6 e7 e11 compared; + e4 e5 e10 decided
    total = r["totals"]
    assert total["type"] == {"agree": 4, "n": 6}                   # e2 wrong; e11 named no Type
    assert total["domains"] == {"agree": 5, "n": 6}                # e2 wrong
    assert total["issues"] == {"agree": 5, "n": 6}                 # e1 partly wrong
    assert total["dyads"] == {"agree": 5, "n": 6}                  # e7 wrong
    assert total["grouping"] == {"agree": 1, "n": 3}               # only e2 e6 e7 proposed a move; e7 right
    assert total["all_three"] == {"agree": 3, "n": 6}              # e3 e6 e7
    assert total["outcome"] == {"accepted": 6, "merged": 1, "rejected": 2}
    a = r["by_extractor"][EXTRACTOR_A]
    assert a["n"] == 3 and a["type"] == {"agree": 2, "n": 3} and a["grouping"] == {"agree": 0, "n": 1}
    assert a["outcome"] == {"accepted": 3, "merged": 1, "rejected": 1}
    b = r["by_extractor"][EXTRACTOR_B]
    assert b["n"] == 3 and b["dyads"] == {"agree": 2, "n": 3} and b["grouping"] == {"agree": 1, "n": 2} and b["type"] == {"agree": 2, "n": 3}
    assert set(r["by_period"]) == {"2025", "2026"} and r["by_period"]["2025"]["n"] == 1 and r["by_period"]["2026"]["n"] == 5
    # the type confusion matrix names what was said and what was decided; a nameless suggestion is in no row
    assert r["type_confusion"]["demonstrative"]["coercive"] == 1 and r["type_confusion"]["coercive"]["coercive"] == 2
    assert sum(sum(c.values()) for c in r["type_confusion"].values()) == 5
    # per-flag detail over the six compared events: issues "military" suggested by e1 e2, on the move for e1 e2 (CN202601)
    assert r["flags"]["issues"]["military"] == {"suggested": 2, "final": 2, "both": 2}
    assert r["flags"]["issues"]["administrative"] == {"suggested": 1, "final": 2, "both": 1}
    assert r["flags"]["issues"]["energy"] == {"suggested": 2, "final": 2, "both": 2}   # e3 e11


def test_empty_report_when_nothing_has_been_reviewed():
    """Seed events carry no extractor and are never counted; an empty list gives the same empty report."""
    moves = [dict(r) for r in csv.DictReader(open(DATA_DIR / "moves.csv", newline="", encoding="utf-8"))]
    events = [dict(r) for r in csv.DictReader(open(DATA_DIR / "events.csv", newline="", encoding="utf-8"))]
    seeds_only = [e for e in events if not e["extractor"]]
    r = agreement.report(seeds_only, moves)
    assert r["n_compared"] == 0 and r["n_decided"] == 0 and r["by_extractor"] == {} and r["totals"]["type"] == {"agree": 0, "n": 0}
    assert agreement.report([], moves) == r


def test_outcomes_alone_when_every_suggestion_was_rejected(fixture):
    moves, events = fixture
    rejected = [dict(e, status="rejected", move_id="", review_note="n") for e in events if e["extractor"]]
    r = agreement.report(rejected, moves)
    assert r["n_compared"] == 0 and r["n_decided"] == 10 and r["totals"]["outcome"] == {"accepted": 0, "merged": 0, "rejected": 10}   # e8 the candidate too


def test_markdown_table(fixture):
    moves, events = fixture
    md = agreement.markdown(agreement.report(events, moves))
    lines = md.splitlines()
    assert lines[0] == "Compared events: 6 (decided suggestions: 9)."
    assert lines[2] == "| Extractor | n | Type | Domains | Issues | Dyads | Grouping | All | accepted | merged | rejected |"
    assert f"| {EXTRACTOR_A} | 3 | 2/3 | 2/3 | 2/3 | 3/3 | 0/1 | 1/3 | 3 | 1 | 1 |" in lines
    assert "| all | 6 | 4/6 | 5/6 | 5/6 | 5/6 | 1/3 | 3/6 | 6 | 1 | 2 |" in lines
    assert "| 2025 | 1 | 1/1 | 1/1 | 1/1 | 0/1 | 1/1 | 1/1 |" in lines


def test_build_regenerates_the_file_and_the_page_renders_it(tmp_path, fixture, browser):
    from web.build import build
    moves, events = fixture
    d = tmp_path / "data"
    shutil.copytree(DATA_DIR, d, ignore=shutil.ignore_patterns("raw"))
    for name, rows in (("moves", moves), ("events", events)):
        with open(d / f"{name}.csv", "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=schema.TABLES[name], lineterminator="\n")
            w.writerows(rows)
    out = tmp_path / "dist"
    build(d, out, build_date="2026-10-20")
    r = json.loads((out / "data/agreement.json").read_text(encoding="utf-8"))
    assert r["n_compared"] == 6 and r["totals"]["type"] == {"agree": 4, "n": 6}
    html = (out / "methodology.html").read_text(encoding="utf-8")
    assert "4 of 6" in html and EXTRACTOR_A in html and "Grouping" in html
    page = browser.new_page()
    problems = []
    page.on("console", lambda m: problems.append((m.type, m.text)) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(("pageerror", str(e))))
    page.goto((out / "methodology.html").resolve().as_uri())
    assert page.locator("#agreement table").count() == 3
    assert page.locator("#agreement .table-scroll[tabindex='0']").count() == 3
    assert not problems, problems
    page.close()


def test_the_built_page_matches_the_report_whatever_the_data_holds(tmp_path):
    """State-independent: the page's empty state appears exactly when the report is empty."""
    from web.build import build
    out = tmp_path / "dist"
    build(DATA_DIR, out, build_date="2026-10-20")
    r = json.loads((out / "data/agreement.json").read_text(encoding="utf-8"))
    moves = [dict(x) for x in csv.DictReader(open(DATA_DIR / "moves.csv", newline="", encoding="utf-8"))]
    events = [dict(x) for x in csv.DictReader(open(DATA_DIR / "events.csv", newline="", encoding="utf-8"))]
    assert r == agreement.report(events, moves)
    html = (out / "methodology.html").read_text(encoding="utf-8")
    assert ("The tables are filled from reviewed harvest runs" in html) == (r["n_decided"] == 0)
