"""Ticket 23: the pre-sort. For every candidate of a run, a suggestion of what the decision is likely to be —
continuation of a move, the same move as another candidate, a new move with its criterion, a duplicate —
with a reason; the review page shows it and prefills the form; the coder decides (ADR 0003)."""
import json
import shutil
from pathlib import Path

import pytest

from pipeline import harvest, presort, queue
from tests.conftest import ROOT, chubb_data

FIX = ROOT / "tests/fixtures/harvest"


@pytest.fixture
def opened(tmp_path):
    base = chubb_data(tmp_path / "base")     # the fixture's 2026 events are its own, not the dataset's
    d = tmp_path / "data"
    d.mkdir()
    for f in ("claimants", "moves", "events", "sources", "corrections"):
        shutil.copy(base / f"{f}.csv", d / f"{f}.csv")
    run = tmp_path / "run"
    assert harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(run),
                         "--recordings", str(FIX / "recordings"), "--run-id", "fixture", "--data", str(base)]) == 0
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


def extend(d, move_id, through):
    """A MATS move made ongoing into the candidates' previous year, in the test's copy of the data."""
    moves = queue.read_table("moves", d)
    for m in moves:
        if m["move_id"] == move_id:
            m["ongoing_through"] = through
    queue.write_table("moves", moves, d)


def test_check_refuses_a_file_that_does_not_fit_the_run(opened, tmp_path):
    extend(opened, "CN201501", "2025")                     # the fixture's candidates are 2026 events
    ids = [c["event_id"] for c in cands(opened)]
    # the only accepted events in the data are Vietnam's (MATS-era seed events); the fixture's VN candidate stands in
    vn = next(c["event_id"] for c in cands(opened) if c["claimant"] == "VN")
    accepted_event = next(e["event_id"] for e in queue.read_table("events", opened) if e["claimant"] == "VN" and e["status"] == "accepted" and e["move_id"])
    good = {"run_id": "fixture", "presorted_by": "test", "date": "2026-11-17", "items": [
        {"event_id": ids[0], "disposition": "new_move", "criterion": "novelty", "reason": "first of its kind"},
        {"event_id": ids[1], "disposition": "same_move", "of": ids[0], "reason": "the same stand-off"},
        {"event_id": ids[2], "disposition": "continuation", "of": "CN201501", "reason": "as in 2015"},
        {"event_id": ids[3], "disposition": "unclear", "reason": "needs the source"},
        {"event_id": ids[4], "disposition": "unclear", "reason": "needs the source"},
    ]}
    # the VN candidate may duplicate an accepted VN event; a CN candidate may not name it
    for it in good["items"]:
        if it["event_id"] == vn:
            it.update({"disposition": "duplicate", "of": accepted_event, "reason": "same report"})
    assert presort.check(good, opened, "fixture") == []
    bad = json.loads(json.dumps(good))
    bad["items"][0]["criterion"] = ""                       # a new move needs its criterion
    bad["items"][2]["of"] = "CN209901"                      # a continuation must name a move that exists
    bad["items"][1]["of"] = "ev-nobody"                     # same_move must name a candidate of the run
    bad["items"][ids.index(vn)]["of"] = ids[2] if ids[2] != vn else ids[0]   # a duplicate names an accepted event, not a candidate
    bad["items"].append({"event_id": "ev-nobody", "disposition": "unclear", "reason": "x"})
    del bad["items"][3]                                     # and every candidate must be covered
    errs = presort.check(bad, opened, "fixture")
    assert any("criterion" in e for e in errs) and any("CN209901" in e for e in errs) and any("ev-nobody" in e for e in errs)
    assert any(ids[3] in e and "missing" in e for e in errs) and any(vn in e and "is same_move" in e for e in errs)
    # a continuation of a move that ended before last year, of a later year, or of another claimant is refused;
    # a same_move chain whose target is not the lead is refused
    late = json.loads(json.dumps(good)); late["items"][2]["of"] = "CN197001"          # ended in 1970
    assert any("ended in" in e for e in presort.check(late, opened, "fixture"))
    chain = json.loads(json.dumps(good)); chain["items"][1]["of"] = ids[3]           # ids[3] is unclear (and CN, 2026), not a lead
    assert any("must itself be the lead" in e for e in presort.check(chain, opened, "fixture"))
    other = json.loads(json.dumps(good)); other["items"][2]["of"] = "VN201501"
    assert any("not an accepted CN move" in e for e in presort.check(other, opened, "fixture"))
    # where last year is undecided, a continuation may name last year's candidate: of this run (earlier year,
    # same claimant) or of the previous run (ids passed in); the label says it is provisional
    prevc = json.loads(json.dumps(good)); prevc["items"][2].update({"of": "ev-prev2025", "reason": "the same practice last year"})
    assert any("ev-prev2025" in e for e in presort.check(prevc, opened, "fixture"))
    assert presort.check(prevc, opened, "fixture", previous_ids={"ev-prev2025"}) == []
    assert presort.label(prevc["items"][2]) == "continuation of ev-prev2025 (a candidate, provisional)"
    samey = json.loads(json.dumps(good)); samey["items"][2].update({"of": ids[0]})          # same year: not earlier
    assert any("earlier year" in e for e in presort.check(samey, opened, "fixture"))


def test_the_review_page_shows_the_presort_and_prefills_the_form(opened, tmp_path):
    extend(opened, "CN201501", "2025")
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
    # prefilled cards are marked and carry a confirm button; the export skips unconfirmed ones
    assert html.count("Confirm the pre-sort") == 3 and 'data-presorted' in html and 'getAttribute("data-presorted") === "1") return' in html
    # a file for another run is refused
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"run_id": "other", "presorted_by": "t", "items": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="not 'fixture'"):
        queue.write_review_page(tmp_path / "x.html", opened, run_id="fixture", presort_path=wrong)


def test_presort_fields_travel_with_the_airtable_records(opened, tmp_path):
    from pipeline import airtable
    ids = [c["event_id"] for c in cands(opened)]
    f = tmp_path / "presort.json"
    f.write_text(json.dumps({"run_id": "fixture", "presorted_by": "test", "date": "2026-11-17", "items": [
        {"event_id": ids[0], "disposition": "continuation", "of": "CN201501", "reason": "as before"}]}), encoding="utf-8")
    recs = airtable.records_for_run(opened, "fixture", presort_path=f)
    r = next(x for x in recs if x["event_id"] == ids[0])
    assert r["presort"].startswith("continuation of CN201501") and "as before" in r["presort"]
    assert sum("presort" in x for x in recs) == 1                       # no placeholder on the others
    # and a push without the file refreshes the other context fields but leaves the base's pre-sort alone
    from tests.test_airtable import FakeAirtable
    fake = FakeAirtable()
    airtable.push(fake, recs, "fixture")
    rid = next(i for i, f in fake.rows.items() if f[fake.wire("event_id")] == ids[0])
    assert fake.rows[rid][fake.wire("presort")].startswith("continuation")
    airtable.push(fake, airtable.records_for_run(opened, "fixture"), "fixture")   # no pre-sort file this time
    assert fake.rows[rid][fake.wire("presort")].startswith("continuation")
