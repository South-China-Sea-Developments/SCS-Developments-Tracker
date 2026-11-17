"""Ticket 23: the pre-sort. For every candidate of a run, a suggestion of what the decision is likely to be —
continuation of a move, the same move as another candidate, a new move with its criterion, a duplicate —
with a reason; the review page shows it and prefills the form; the coder decides (ADR 0003)."""
import json
import shutil
from pathlib import Path

import pytest

from pipeline import harvest, presort, queue
from tests.conftest import DATA_DIR, ROOT

FIX = ROOT / "tests/fixtures/harvest"


@pytest.fixture
def opened(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    for f in ("claimants", "moves", "events", "sources", "corrections"):
        shutil.copy(DATA_DIR / f"{f}.csv", d / f"{f}.csv")
    run = tmp_path / "run"
    assert harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(run),
                         "--recordings", str(FIX / "recordings"), "--run-id", "fixture"]) == 0
    assert queue.append_run(run, d)[0] == 5
    return d


def cands(d):
    return [e for e in queue.read_table("events", d) if e["status"] == "candidate" and e["harvest_run_id"] == "fixture"]


def test_context_gives_the_presorter_the_candidates_and_the_previous_year(opened):
    ctx = presort.context(opened, "fixture")
    assert ctx["run_id"] == "fixture" and len(ctx["candidates"]) == 5
    c = ctx["candidates"][0]
    assert {"event_id", "claimant", "date_start", "summary", "suggested_type", "sources"} <= set(c)
    assert c["sources"] and "title" in c["sources"][0] and "excerpt" not in c["sources"][0]   # titles only; the page has the excerpts
    # for each claimant-year in the run, the previous year's and the same year's accepted moves
    years = {(c["claimant"], c["date_start"][:4]) for c in ctx["candidates"]}
    assert all(f"{cl}:{int(y) - 1}" in ctx["moves"] for cl, y in years)
    assert ctx["dispositions"] == presort.DISPOSITIONS


def test_check_refuses_a_file_that_does_not_fit_the_run(opened, tmp_path):
    ids = [c["event_id"] for c in cands(opened)]
    good = {"run_id": "fixture", "presorted_by": "test", "date": "2026-11-17", "items": [
        {"event_id": ids[0], "disposition": "new_move", "criterion": "novelty", "reason": "first of its kind"},
        {"event_id": ids[1], "disposition": "same_move", "of": ids[0], "reason": "the same stand-off"},
        {"event_id": ids[2], "disposition": "continuation", "of": "CN201501", "reason": "as in 2015"},
        {"event_id": ids[3], "disposition": "duplicate", "of": ids[2], "reason": "same report"},
        {"event_id": ids[4], "disposition": "unclear", "reason": "needs the source"},
    ]}
    assert presort.check(good, opened, "fixture") == []
    bad = json.loads(json.dumps(good))
    bad["items"][0]["criterion"] = ""                       # a new move needs its criterion
    bad["items"][2]["of"] = "CN209901"                      # a continuation must name a move that exists
    bad["items"][1]["of"] = "ev-nobody"                     # same_move must name a candidate of the run
    bad["items"].append({"event_id": "ev-nobody", "disposition": "unclear", "reason": "x"})
    del bad["items"][4]                                     # and every candidate must be covered
    errs = presort.check(bad, opened, "fixture")
    assert any("criterion" in e for e in errs) and any("CN209901" in e for e in errs) and any("ev-nobody" in e for e in errs)
    assert any(ids[4] in e and "missing" in e for e in errs)


def test_the_review_page_shows_the_presort_and_prefills_the_form(opened, tmp_path):
    ids = [c["event_id"] for c in cands(opened)]
    f = tmp_path / "presort.json"
    f.write_text(json.dumps({"run_id": "fixture", "presorted_by": "test", "date": "2026-11-17", "items": [
        {"event_id": ids[0], "disposition": "new_move", "criterion": "scope", "reason": "a new area for the coast guard"},
        {"event_id": ids[1], "disposition": "continuation", "of": "CN201501", "reason": "the standing patrol pattern"},
        {"event_id": ids[2], "disposition": "same_move", "of": ids[0], "reason": "the same stand-off"},
    ]}), encoding="utf-8")
    page = tmp_path / "review.html"
    assert queue.write_review_page(page, opened, run_id="fixture", presort_path=f) == 5
    html = page.read_text(encoding="utf-8")
    assert "pre-sort: new move (scope)" in html and "a new area for the coast guard" in html
    assert "pre-sort: continuation of CN201501" in html and "pre-sort: same move as " + ids[0] in html
    assert '"disposition": "continuation", "of": "CN201501"' in html      # in the page's JSON, for the JS prefill
    assert "presorted by test" in html
    # a candidate without a pre-sort line is simply shown without one
    assert html.count("pre-sort:") == 3


def test_presort_fields_travel_with_the_airtable_records(opened, tmp_path):
    from pipeline import airtable
    ids = [c["event_id"] for c in cands(opened)]
    f = tmp_path / "presort.json"
    f.write_text(json.dumps({"run_id": "fixture", "presorted_by": "test", "date": "2026-11-17", "items": [
        {"event_id": ids[0], "disposition": "continuation", "of": "CN201501", "reason": "as before"}]}), encoding="utf-8")
    recs = airtable.records_for_run(opened, "fixture", presort_path=f)
    r = next(x for x in recs if x["event_id"] == ids[0])
    assert r["presort"].startswith("continuation of CN201501") and "as before" in r["presort"]
    assert all("presort" in x for x in recs)
