"""Seam 1: the review queue. A fixture run is appended to a copy of the data, every decision type is
applied, and the files end up in the expected state and pass the validator."""
import csv
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline import airtable, harvest, queue, schema
from pipeline.validate import validate
from tests.conftest import DATA_DIR, RAW_MAVD, RAW_XLSX, ROOT

FIX = ROOT / "tests/fixtures/harvest"
REVIEWER, DATE = "Test Coder", "2026-10-15"


def rows(d: Path, name: str) -> list[dict]:
    with open(d / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def opened(tmp_path):
    """A data copy with the fixture run's five candidates appended, as `queue open` leaves it."""
    d = tmp_path / "data"
    d.mkdir()
    for f in ("claimants", "moves", "events", "sources", "corrections"):
        shutil.copy(DATA_DIR / f"{f}.csv", d / f"{f}.csv")
    run = tmp_path / "run"
    assert harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(run),
                         "--recordings", str(FIX / "recordings"), "--run-id", "fixture"]) == 0
    assert queue.append_run(run, d) == (5, 5)
    assert queue.append_run(run, d) == (0, 0)          # idempotent: a second open adds nothing
    return d


def candidates(d):
    return [r for r in rows(d, "events") if r["status"] == "candidate" and r["harvest_run_id"] == "fixture"]


def test_open_appends_candidates_that_pass_the_validator(opened):
    c = candidates(opened)
    assert len(c) == 5 and {x["claimant"] for x in c} == {"CN", "VN"}
    assert validate(opened, RAW_XLSX, RAW_MAVD) == []


def test_open_places_candidates_whose_feature_the_gazetteer_knows(opened):
    """Ticket 08: a named feature becomes coordinates and a sub-region at open; an unnamed one stays unplaced."""
    by_name = {x["location_name"][:12]: x for x in candidates(opened)}
    stas = by_name["Second Thoma"]
    assert (stas["lat"], stas["lon"], stas["subregion"], stas["location_precision"]) == ("9.65000", "115.85000", "6", "feature")
    scar = by_name["Scarborough "]
    assert scar["subregion"] == "4" and float(scar["lat"]) == pytest.approx(15.18, abs=0.02)
    headline = by_name[""]
    assert headline["lat"] == "" and headline["location_precision"] in ("", "unknown")


def test_edited_locations_are_resolved_again(opened):
    """A corrected name is placed afresh (old coordinates do not survive it); typed coordinates get
    their sub-region from the polygons; an unknown name clears the position."""
    cands = candidates(opened)
    stas = next(x for x in cands if x["location_name"].startswith("Second"))
    assert stas["subregion"] == "6"
    out = queue._check_edits(stas["event_id"], stas, {"location_name": "Whitsun Reef"})
    assert (out["lat"], out["subregion"], out["location_precision"]) == ("9.96667", "5", "feature")
    out = queue._check_edits(stas["event_id"], stas, {"location_name": "somewhere in the sea"})
    assert (out["lat"], out["lon"], out["location_precision"]) == ("", "", "subregion") and "subregion" not in out   # sub-region 6 kept
    out = queue._check_edits(stas["event_id"], stas, {"location_name": "Whitsun Reef", "subregion": "7"})
    assert out["lat"] == "9.96667" and out["subregion"] == "7"      # the reviewer's sub-region stands; the validator will judge the pair
    out = queue._check_edits(stas["event_id"], stas, {"location_name": "North Reef"})       # ambiguous: unplaced, reviewer decides
    assert out["lat"] == "" and out["location_precision"] == "subregion"
    out = queue._check_edits(stas["event_id"], stas, {"lat": "15.18", "lon": "117.77"})
    assert out["subregion"] == "4" and "location_precision" not in out      # feature stays feature
    out = queue._check_edits(stas["event_id"], dict(stas, location_precision="unknown"), {"lat": "15.18", "lon": "117.77", "subregion": "3"})
    assert out["subregion"] == "3" and out["location_precision"] == "point"   # a stated sub-region is kept for the validator to judge
    unplaced = dict(stas, lat="", lon="", location_precision="unknown")
    with pytest.raises(ValueError, match="go together"):
        queue._check_edits(stas["event_id"], unplaced, {"lat": "9.5"})
    with pytest.raises(ValueError, match="needs coordinates"):
        queue._check_edits(stas["event_id"], unplaced, {"location_precision": "point"})


def test_review_page_shows_what_the_coder_needs(opened, tmp_path):
    page = tmp_path / "review.html"
    assert queue.write_review_page(page, opened, run_id="fixture") == 5
    html = page.read_text(encoding="utf-8")
    assert html.count('class="cand"') == 5
    assert "Second Thomas Shoal" in html and "possible duplicate of" in html
    assert "China's moves open through 2025" in html and "None recorded." in html     # no CN move runs that late yet
    assert "Vietnam's moves open through 2025" in html
    assert "form a new move" in html and "Intensification criterion" in html
    assert "fmprc.gov.cn" in html                                          # source link and excerpt
    assert "Physical interference" in html                                  # the extractor's reasoning
    # no candidates -> an empty page, not an error
    assert queue.write_review_page(tmp_path / "empty.html", opened, run_id="no-such-run") == 0


def test_every_decision_type_yields_the_expected_files(opened):
    cands = candidates(opened)
    pick = lambda prefix: next(x for x in cands if x["location_name"].startswith(prefix))
    stas, scar, thitu = pick("Second"), pick("Scarb"), pick("Thitu")
    vn = next(x for x in cands if x["claimant"] == "VN")
    headline = next(x for x in cands if not x["location_name"])
    decisions = [
        {"event_id": scar["event_id"], "action": "new_move", "note": "First physical interference at Scarborough this year.",
         "new_move": {"type": "coercive", "intensification_criterion": "frequency", "domains": ["physical"],
                      "issues": ["military", "administrative"], "dyads": ["CP"], "subregions": ["4"],
                      "description": "2026, October 4: CCG and PLA units interfere with Philippine aircraft and vessels near Scarborough Shoal (MFA remarks, 6 Oct 2026).",
                      "ongoing_through": "2026"}},
        {"event_id": thitu["event_id"], "action": "merge", "move_of_event": scar["event_id"], "note": "Same operation, second area.",
         "edits": {"summary": "Same-day interference near Thitu Island and Sandy Cay.", "subregion": "5", "lat": ""}},
        {"event_id": stas["event_id"], "action": "new_move",
         "new_move": {"type": "coercive", "intensification_criterion": "novelty", "domains": ["physical"], "issues": ["military"], "dyads": ["CP"], "subregions": ["6"]}},
        {"event_id": headline["event_id"], "action": "reject", "note": "Headline only; incident location unknown, possibly outside the South China Sea."},
        {"event_id": vn["event_id"], "action": "new_move",
         "new_move": {"type": "declarative", "intensification_criterion": "novelty", "domains": ["diplomatic"], "issues": ["politics"], "dyads": ["VC"], "subregions": ["2"],
                      "year": "2026"}},
    ]
    counts = queue.apply_decisions(decisions, REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert counts == {"rejected": 1, "merged": 1, "new_moves": 3, "duplicates": 0, "accepted_events": 4, "extended": 0}

    ev = {e["event_id"]: e for e in rows(opened, "events")}
    mv = {m["move_id"]: m for m in rows(opened, "moves")}
    # new moves: ids follow the MATS form and instance numbering per claimant-year, in events.csv order
    # (the Second Thomas candidate precedes the Scarborough one in the file, whatever the order of the decisions)
    assert ev[stas["event_id"]]["move_id"] == "CN202601" and ev[scar["event_id"]]["move_id"] == "CN202602"
    assert ev[vn["event_id"]]["move_id"] == "VN202601"
    m = mv["CN202602"]
    assert m["coercive"] == "1" and m["declarative"] == "0" and m["physical"] == "1" and m["loc04_central_east"] == "1"
    assert m["dyads"] == "CP" and m["intensification_criterion"] == "frequency" and m["coded_by"] == "project"
    assert m["coder"] == REVIEWER and m["coding_date"] == DATE and m["data_version"] == schema.DATASET_VERSION and m["status"] == "accepted"
    assert m["description"].startswith("2026, October 4")
    assert mv["CN202601"]["description"] == stas["summary"]       # description defaults to the event summary
    # merged event: joined the new move, edits applied, provenance recorded
    t = ev[thitu["event_id"]]
    assert t["status"] == "accepted" and t["move_id"] == "CN202602" and t["subregion"] == "5"
    assert t["summary"] == "Same-day interference near Thitu Island and Sandy Cay."
    assert t["reviewer"] == REVIEWER and t["review_date"] == DATE
    assert t["review_note"].startswith("Possible duplicate of ") and t["review_note"].endswith("| Reviewer: Same operation, second area.")
    # suggestions survive beside the final coding (agreement log)
    assert t["suggested_type"] == "coercive" and t["suggestion_reasoning"]
    # rejected: stays in the file with its note
    h = ev[headline["event_id"]]
    assert h["status"] == "rejected" and h["move_id"] == "" and "Headline only" in h["review_note"]
    # the whole thing passes the merge gate
    assert validate(opened, RAW_XLSX, RAW_MAVD) == []
    # and nothing about MATS changed
    assert sum(1 for x in mv.values() if x["coded_by"] == "chubb") == 358


NEW = {"type": "coercive", "intensification_criterion": "novelty", "subregions": ["4"]}


@pytest.mark.parametrize("bad, message", [
    ({"action": "reject"}, "needs a note"),
    ({"action": "merge", "move_id": "ZZ000099"}, "does not exist"),
    ({"action": "merge", "move_id": "VN201501"}, "cannot merge a CN event"),            # cross-claimant
    ({"action": "merge", "move_id": "CN201501"}, "dated 2026-10-08 but move CN201501 is 2015"),
    ({"action": "merge", "move_of_event": "ev-nobody"}, "does not form a new move"),
    ({"action": "new_move", "new_move": {"type": "coercive"}}, "intensification_criterion"),
    ({"action": "new_move", "new_move": {"type": "wrong", "intensification_criterion": "novelty"}}, "exactly one type"),
    ({"action": "new_move", "new_move": dict(NEW, dyads=["CN PH"])}, "dyads must be"),
    ({"action": "new_move", "new_move": dict(NEW, domains=["kinetic"])}, "unknown domains"),
    ({"action": "new_move", "new_move": dict(NEW, subregions=["42"])}, "sub-regions must be"),
    ({"action": "new_move", "new_move": dict(NEW, move_id="PH209901")}, "must have the form CN2026NN"),
    ({"action": "new_move", "new_move": dict(NEW, ongoing_through="1999")}, "ongoing_through"),
    ({"action": "new_move", "new_move": NEW, "edits": {"status": "accepted"}}, "not editable"),
    ({"action": "new_move", "new_move": NEW, "edits": {"date_start": "2026-13-45"}}, "not an ISO date"),
    ({"action": "new_move", "new_move": NEW, "edits": {"date_end": "2026-01-01"}}, "date_end is before"),
    ({"action": "new_move", "new_move": NEW, "edits": {"lat": "abc"}}, "not a number"),
    ({"action": "new_move", "new_move": NEW, "edits": {"subregion": "42"}}, "subregion must be"),
    ({"action": "duplicate", "duplicate_of": "VN197301-E01"}, "names a VN event"),
    ({"action": "duplicate", "duplicate_of": "ev-nobody"}, "must name an accepted event"),
    ({"action": "fly"}, "unknown action"),
])
def test_invalid_decisions_are_refused_and_nothing_is_written(opened, bad, message):
    before = (opened / "events.csv").read_bytes(), (opened / "moves.csv").read_bytes()
    eid = next(x for x in candidates(opened) if x["location_name"].startswith("Second"))["event_id"]
    with pytest.raises(ValueError, match=message):
        queue.apply_decisions([dict(bad, event_id=eid)], REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert ((opened / "events.csv").read_bytes(), (opened / "moves.csv").read_bytes()) == before


def test_duplicate_decision_marks_the_event_merged_into_the_same_move(opened):
    cands = candidates(opened)
    scar = next(x for x in cands if x["location_name"].startswith("Scarb"))
    thitu = next(x for x in cands if x["location_name"].startswith("Thitu"))
    queue.apply_decisions([{"event_id": scar["event_id"], "action": "new_move", "new_move": NEW}], REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    counts = queue.apply_decisions([{"event_id": thitu["event_id"], "action": "duplicate", "duplicate_of": scar["event_id"], "note": "same report"}],
                                   REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert counts["duplicates"] == 1
    e = {x["event_id"]: x for x in rows(opened, "events")}[thitu["event_id"]]
    assert e["status"] == "merged" and e["move_id"] == "CN202601"
    assert e["review_note"].endswith(f"| Reviewer: Duplicate of {scar['event_id']}. same report")
    assert validate(opened, RAW_XLSX, RAW_MAVD) == []


def test_a_merge_into_a_rejected_lead_is_rejected_with_it(opened):
    """A merge whose lead candidate is rejected cannot form a move: the merge becomes a rejection of its own,
    in the same batch, transitively, and when the lead was rejected in an earlier batch."""
    cands = candidates(opened)
    pick = lambda prefix: next(x for x in cands if x["location_name"].startswith(prefix))
    stas, scar, thitu = pick("Second"), pick("Scarb"), pick("Thitu")
    headline = next(x for x in cands if not x["location_name"])
    decisions = [
        {"event_id": scar["event_id"], "action": "reject", "note": "Routine presence, no intensification."},
        {"event_id": thitu["event_id"], "action": "merge", "move_of_event": scar["event_id"], "note": "Same operation, second area."},
        {"event_id": stas["event_id"], "action": "merge", "move_of_event": thitu["event_id"]},     # chained through thitu
    ]
    counts = queue.apply_decisions(decisions, REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert counts == {"rejected": 3, "merged": 0, "new_moves": 0, "duplicates": 0, "accepted_events": 0, "extended": 0}
    ev = {e["event_id"]: e for e in rows(opened, "events")}
    t, s = ev[thitu["event_id"]], ev[stas["event_id"]]
    assert t["status"] == "rejected" and t["move_id"] == "" and t["reviewer"] == REVIEWER
    assert t["review_note"].endswith(f"| Reviewer: Rejected with {scar['event_id']}: the candidate it would merge into was rejected. Same operation, second area.")
    assert s["status"] == "rejected" and f"Rejected with {thitu['event_id']}" in s["review_note"]
    # the next batch: a merge into a lead rejected earlier, and a duplicate of a rejected event, go the same way
    counts = queue.apply_decisions([{"event_id": headline["event_id"], "action": "merge", "move_of_event": scar["event_id"]}],
                                   REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert counts["rejected"] == 1 and counts["merged"] == 0
    vn = next(x for x in cands if x["claimant"] == "VN")
    counts = queue.apply_decisions([{"event_id": vn["event_id"], "action": "duplicate", "duplicate_of": headline["event_id"]}],
                                   REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert counts["rejected"] == 1 and counts["duplicates"] == 0
    ev = {e["event_id"]: e for e in rows(opened, "events")}
    assert ev[headline["event_id"]]["status"] == "rejected" and ev[vn["event_id"]]["status"] == "rejected"
    assert ev[vn["event_id"]]["review_note"].endswith(f"Rejected with {headline['event_id']}: the event it duplicates was rejected.")
    assert validate(opened, RAW_XLSX, RAW_MAVD) == []
    # (a merge into a lead decided anything else than new_move or reject is still refused: see the parametrized case)


def test_a_batch_whose_result_fails_the_gate_writes_nothing(opened):
    """Two decisions in one batch; the second is valid on its own but the validator must see the whole result."""
    eid = next(x for x in candidates(opened) if x["location_name"].startswith("Second"))["event_id"]
    before = (opened / "events.csv").read_bytes()
    with pytest.raises(ValueError, match="more than one decision"):
        queue.apply_decisions([{"event_id": eid, "action": "reject", "note": "a"}, {"event_id": eid, "action": "reject", "note": "b"}],
                              REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert (opened / "events.csv").read_bytes() == before


def test_decided_events_cannot_be_decided_twice(opened):
    eid = candidates(opened)[0]["event_id"]
    queue.apply_decisions([{"event_id": eid, "action": "reject", "note": "no"}], REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    with pytest.raises(ValueError, match="not a candidate"):
        queue.apply_decisions([{"event_id": eid, "action": "reject", "note": "again"}], REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)


def test_validator_requires_a_criterion_on_project_moves(opened):
    eid = candidates(opened)[0]["event_id"]
    queue.apply_decisions([{"event_id": eid, "action": "new_move",
                            "new_move": {"type": "coercive", "intensification_criterion": "scope", "subregions": ["4"]}}], REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    mrows = rows(opened, "moves")
    for m in mrows:
        if m["coded_by"] == "project":
            m["intensification_criterion"] = ""
    queue.write_table("moves", mrows, opened)
    assert any("without an intensification_criterion" in e for e in validate(opened, RAW_XLSX, RAW_MAVD))


def test_open_and_decide_end_to_end_in_a_git_checkout(tmp_path):
    """The CLI path: a clone, `open --no-push` makes a branch and a commit, `decide` makes a second commit."""
    import os, sys
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(ROOT), str(clone)], check=True, env=env)
    # the code under test is the working tree, committed or not
    shutil.rmtree(clone / "pipeline")
    shutil.copytree(ROOT / "pipeline", clone / "pipeline", ignore=shutil.ignore_patterns("__pycache__"))
    run = clone / "harvest" / "runs" / "fixture"
    assert harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(run),
                         "--recordings", str(FIX / "recordings"), "--run-id", "fixture"]) == 0
    r = subprocess.run([sys.executable, "-m", "pipeline.queue", "open", "--run", str(run), "--no-push"], cwd=clone, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert subprocess.run(["git", "-C", str(clone), "branch", "--show-current"], capture_output=True, text=True).stdout.strip() == "harvest/fixture"
    # running open again resumes the branch and adds nothing
    r = subprocess.run([sys.executable, "-m", "pipeline.queue", "open", "--run", str(run), "--no-push"], cwd=clone, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and "resuming" in r.stdout and "0 new candidate" in r.stdout
    assert (clone / "docs/review/fixture.html").exists()
    log = subprocess.run(["git", "-C", str(clone), "log", "--oneline", "-1"], capture_output=True, text=True).stdout
    assert "Harvest fixture: 5 candidate events" in log
    eid = [e for e in rows(clone / "data", "events") if e["status"] == "candidate" and e["harvest_run_id"] == "fixture"][0]["event_id"]
    (clone / "decisions.json").write_text(json.dumps({"decisions": [{"event_id": eid, "action": "reject", "note": "test"}]}), encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "pipeline.queue", "decide", "decisions.json", "--reviewer", "T", "--date", DATE], cwd=clone, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    log = subprocess.run(["git", "-C", str(clone), "log", "--oneline", "-2"], capture_output=True, text=True).stdout
    assert "Review by T: 1 rejected" in log
    # an invalid file applies nothing and says why
    (clone / "bad.json").write_text(json.dumps({"decisions": [{"event_id": "ev-nobody", "action": "reject", "note": "x"}]}), encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "pipeline.queue", "decide", "bad.json", "--reviewer", "T"], cwd=clone, capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "nothing applied" in r.stderr
    assert validate(clone / "data", RAW_XLSX, RAW_MAVD) == []


# ---------------------------------------------------------------------------
# ticket 24: a continuation note extends the move it names

def test_a_continuation_note_extends_the_named_moves_ongoing_through(opened):
    cands = candidates(opened)
    cn = [x for x in cands if x["claimant"] == "CN"]
    scar = next(x for x in cn if x["location_name"].startswith("Scarb"))
    thitu = next(x for x in cn if x["location_name"].startswith("Thitu"))
    headline = next(x for x in cn if not x["location_name"])
    moves = rows(opened, "moves")            # fix the reach of the two moves, whatever later decisions did to the live file
    for m in moves:
        if m["move_id"] in ("CN201504", "CN201501"):
            m["ongoing_through"] = {"CN201504": "2018", "CN201501": "2016"}[m["move_id"]]
    queue.write_table("moves", moves, opened)
    corr = [c for c in rows(opened, "corrections") if c["move_id"] not in ("CN201504", "CN201501") or c["field"] != "ongoing_through"]
    queue.write_table("corrections", corr, opened)
    before = {m["move_id"]: m for m in rows(opened, "moves")}
    assert before["CN201504"]["coded_by"] == "chubb"
    counts = queue.apply_decisions([
        {"event_id": scar["event_id"], "action": "reject", "note": "continuation of CN201504 (pre-sort confirmed)"},
        {"event_id": thitu["event_id"], "action": "reject", "note": "continuation of CN201504 — same practice"},
        {"event_id": headline["event_id"], "action": "reject", "note": "Continuation of CN201501."},   # through 2016: extended too; case and stop tolerated
    ], REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert counts["rejected"] == 3 and counts["extended"] == 2
    after = {m["move_id"]: m for m in rows(opened, "moves")}
    assert after["CN201504"]["ongoing_through"] == "2026" and after["CN201501"]["ongoing_through"] == "2026"
    corr = [c for c in rows(opened, "corrections") if c["field"] == "ongoing_through" and c["date"] == DATE]
    assert {(c["move_id"], c["new_value"], c["by"], c["date"]) for c in corr} == {("CN201504", "2026", REVIEWER, DATE), ("CN201501", "2026", REVIEWER, DATE)}
    assert all(c["reason"].startswith("continuation: ev-") for c in corr)
    assert validate(opened, RAW_XLSX, RAW_MAVD) == []          # the guarded change is documented
    # the events keep the note; nothing else about them changed
    assert all(x["status"] == "rejected" for x in rows(opened, "events") if x["event_id"] in (scar["event_id"], thitu["event_id"]))


def test_a_continuation_note_may_name_a_candidate_whose_move_exists(opened):
    cands = candidates(opened)
    scar = next(x for x in cands if x["location_name"].startswith("Scarb"))
    thitu = next(x for x in cands if x["location_name"].startswith("Thitu"))
    queue.apply_decisions([{"event_id": scar["event_id"], "action": "new_move",
                            "new_move": {"type": "coercive", "intensification_criterion": "novelty", "domains": ["physical"],
                                         "issues": ["military"], "dyads": ["CP"], "subregions": ["4"]}}], REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    # a later sitting: the follower is a continuation of the lead candidate, same year → nothing to extend
    counts = queue.apply_decisions([{"event_id": thitu["event_id"], "action": "reject", "note": f"continuation of {scar['event_id']} (pre-sort confirmed)"}],
                                   REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert counts["rejected"] == 1 and counts["extended"] == 0
    # a year no later than the move's extends nothing, and a second sitting adds no second corrections row
    assert queue.apply_decisions([{"event_id": next(x for x in cands if x["claimant"] == "VN")["event_id"], "action": "reject",
                                   "note": "continuation of VN201501 (pre-sort confirmed)"}], REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)["extended"] == 1
    assert len([c for c in rows(opened, "corrections") if c["move_id"] == "VN201501"]) == 1
    # a note naming a move that does not exist is a mistake the batch must not swallow
    headline = next(x for x in cands if not x["location_name"])
    with pytest.raises(ValueError, match="continuation of CN199999"):
        queue.apply_decisions([{"event_id": headline["event_id"], "action": "reject", "note": "continuation of CN199999"}],
                              REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    with pytest.raises(ValueError, match="not an event"):
        queue.apply_decisions([{"event_id": headline["event_id"], "action": "reject", "note": "continuation of ev-doesnotexist"}],
                              REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    # and a move of another claimant cannot be the continuation target
    with pytest.raises(ValueError, match="VN"):
        queue.apply_decisions([{"event_id": headline["event_id"], "action": "reject", "note": "continuation of VN201501"}],
                              REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)


def test_a_follower_of_a_lead_decided_in_the_same_batch_resolves_through_it(opened):
    cands = candidates(opened)
    scar = next(x for x in cands if x["location_name"].startswith("Scarb"))
    thitu = next(x for x in cands if x["location_name"].startswith("Thitu"))
    counts = queue.apply_decisions([
        {"event_id": scar["event_id"], "action": "new_move",
         "new_move": {"type": "coercive", "intensification_criterion": "novelty", "domains": ["physical"], "issues": ["military"], "dyads": ["CP"], "subregions": ["4"]}},
        {"event_id": thitu["event_id"], "action": "reject", "note": f"continuation of {scar['event_id']}"},
    ], REVIEWER, DATE, opened, RAW_XLSX, RAW_MAVD)
    assert counts["new_moves"] == 1 and counts["rejected"] == 1 and counts["extended"] == 0   # same year: nothing to extend, no error



def test_the_previous_year_list_holds_every_move_open_through_that_year(opened):
    """A continuation target is usually an older move still running (CN200802, 2008, open through 2015),
    not a move coded in the previous year; the list shows all of them, newest first, with their reach."""
    moves = rows(opened, "moves")
    for m in moves:                                   # let two old moves run into the fixture's year (2026)
        if m["move_id"] in ("CN201403", "CN201504"):
            m["ongoing_through"] = "2025"
    queue.write_table("moves", moves, opened)
    ctx = queue.review_context(opened, "fixture")
    cn = next(it for it in ctx["items"] if it["event"]["claimant"] == "CN")
    ids = [m["move_id"] for m in cn["previous_year_moves"]]
    assert ids == ["CN201504", "CN201403"]            # open through 2025; CN201501 (through 2016) is not
    assert "through 2025" in airtable._moves_text(cn["previous_year_moves"])


def test_sync_data_keeps_mains_version_of_shared_rows_and_the_branchs_own(tmp_path):
    """Ticket 26: after a union merge, a row both sides hold appears twice; main's version wins."""
    from pipeline import sync_data
    main_rows = [{"move_id": "CN201605", "loc08_spratly_sw": "1"}, {"move_id": "CN201504", "loc08_spratly_sw": "1"}]
    working = [{"move_id": "CN201605", "loc08_spratly_sw": "1"}, {"move_id": "CN201605", "loc08_spratly_sw": "0"},
               {"move_id": "CN201504", "loc08_spratly_sw": "1"}, {"move_id": "CN201701", "loc08_spratly_sw": "0"},
               {"move_id": "CN201701", "loc08_spratly_sw": "0"}]
    out = sync_data.merged(main_rows, working, ("move_id",))
    assert out == main_rows + [{"move_id": "CN201701", "loc08_spratly_sw": "0"}]


def test_a_retired_move_id_is_never_reused(tmp_path, monkeypatch):
    """A retracted move's id stays a gap: the next 2017 China move skips it, and the validator refuses it."""
    retired = tmp_path / "retired.csv"
    retired.write_text("move_id,date,by,reason\nCN201702,2026-11-20,T,test\n", encoding="utf-8")
    monkeypatch.setattr(queue, "RETIRED", retired)
    monkeypatch.setattr(queue.retired_move_ids, "__defaults__", (retired,))
    moves = [{"move_id": "CN201701"}, {"move_id": "CN201703"}]
    assert queue.next_move_id("CN", 2017, moves) == "CN201704"
    assert queue.next_move_id("CN", 2018, moves) == "CN201801"

