"""Seam 1: the review queue. A fixture run is appended to a copy of the data, every decision type is
applied, and the files end up in the expected state and pass the validator."""
import csv
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline import harvest, queue, schema
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


def test_review_page_shows_what_the_coder_needs(opened, tmp_path):
    page = tmp_path / "review.html"
    assert queue.write_review_page(page, opened, run_id="fixture") == 5
    html = page.read_text(encoding="utf-8")
    assert html.count('class="cand"') == 5
    assert "Second Thomas Shoal" in html and "possible duplicate of" in html
    assert "China's moves in 2025" in html and "None recorded." in html     # previous-year moves (none coded yet)
    assert "Vietnam's moves in 2025" in html
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
        {"event_id": thitu["event_id"], "action": "merge", "move_id": "CN202601", "note": "Same operation, second area.",
         "edits": {"summary": "Same-day interference near Thitu Island and Sandy Cay.", "subregion": "5"}},
        {"event_id": stas["event_id"], "action": "new_move",
         "new_move": {"type": "coercive", "intensification_criterion": "novelty", "domains": ["physical"], "issues": ["military"], "dyads": ["CP"], "subregions": ["6"]}},
        {"event_id": headline["event_id"], "action": "reject", "note": "Headline only; incident location unknown, possibly outside the South China Sea."},
        {"event_id": vn["event_id"], "action": "new_move",
         "new_move": {"type": "declarative", "intensification_criterion": "novelty", "domains": ["diplomatic"], "issues": ["politics"], "dyads": ["VC"], "subregions": ["2"],
                      "year": "2026"}},
    ]
    counts = queue.apply_decisions(decisions, REVIEWER, DATE, opened)
    assert counts == {"rejected": 1, "merged": 1, "new_moves": 3, "accepted_events": 4}

    ev = {e["event_id"]: e for e in rows(opened, "events")}
    mv = {m["move_id"]: m for m in rows(opened, "moves")}
    # new moves: ids follow the MATS form and instance numbering per claimant-year
    assert ev[scar["event_id"]]["move_id"] == "CN202601" and ev[stas["event_id"]]["move_id"] == "CN202602"
    assert ev[vn["event_id"]]["move_id"] == "VN202601"
    m = mv["CN202601"]
    assert m["coercive"] == "1" and m["declarative"] == "0" and m["physical"] == "1" and m["loc04_central_east"] == "1"
    assert m["dyads"] == "CP" and m["intensification_criterion"] == "frequency" and m["coded_by"] == "project"
    assert m["coder"] == REVIEWER and m["coding_date"] == DATE and m["data_version"] == schema.DATASET_VERSION and m["status"] == "accepted"
    assert m["description"].startswith("2026, October 4")
    assert mv["CN202602"]["description"] == stas["summary"]       # description defaults to the event summary
    # merged event: joined the new move, edits applied, provenance recorded
    t = ev[thitu["event_id"]]
    assert t["status"] == "accepted" and t["move_id"] == "CN202601" and t["subregion"] == "5"
    assert t["summary"] == "Same-day interference near Thitu Island and Sandy Cay."
    assert t["reviewer"] == REVIEWER and t["review_date"] == DATE
    assert t["review_note"].startswith("Possible duplicate of ") and t["review_note"].endswith("Same operation, second area.")
    # suggestions survive beside the final coding (agreement log)
    assert t["suggested_type"] == "coercive" and t["suggestion_reasoning"]
    # rejected: stays in the file with its note
    h = ev[headline["event_id"]]
    assert h["status"] == "rejected" and h["move_id"] == "" and "Headline only" in h["review_note"]
    # the whole thing passes the merge gate
    assert validate(opened, RAW_XLSX, RAW_MAVD) == []
    # and nothing about MATS changed
    assert sum(1 for x in mv.values() if x["coded_by"] == "chubb") == 358


@pytest.mark.parametrize("bad, message", [
    ({"action": "reject"}, "needs a note"),
    ({"action": "merge", "move_id": "ZZ000099"}, "does not exist"),
    ({"action": "new_move", "new_move": {"type": "coercive"}}, "intensification_criterion"),
    ({"action": "new_move", "new_move": {"type": "wrong", "intensification_criterion": "novelty"}}, "exactly one type"),
    ({"action": "new_move", "new_move": {"type": "coercive", "intensification_criterion": "novelty"}, "edits": {"status": "accepted"}}, "not editable"),
    ({"action": "fly"}, "unknown action"),
])
def test_invalid_decisions_are_refused_and_nothing_is_written(opened, bad, message):
    before = (opened / "events.csv").read_bytes(), (opened / "moves.csv").read_bytes()
    eid = candidates(opened)[0]["event_id"]
    with pytest.raises(ValueError, match=message):
        queue.apply_decisions([dict(bad, event_id=eid)], REVIEWER, DATE, opened)
    assert ((opened / "events.csv").read_bytes(), (opened / "moves.csv").read_bytes()) == before


def test_decided_events_cannot_be_decided_twice(opened):
    eid = candidates(opened)[0]["event_id"]
    queue.apply_decisions([{"event_id": eid, "action": "reject", "note": "no"}], REVIEWER, DATE, opened)
    with pytest.raises(ValueError, match="not a candidate"):
        queue.apply_decisions([{"event_id": eid, "action": "reject", "note": "again"}], REVIEWER, DATE, opened)


def test_validator_requires_a_criterion_on_project_moves(opened):
    eid = candidates(opened)[0]["event_id"]
    queue.apply_decisions([{"event_id": eid, "action": "new_move",
                            "new_move": {"type": "coercive", "intensification_criterion": "scope"}}], REVIEWER, DATE, opened)
    mrows = rows(opened, "moves")
    for m in mrows:
        if m["coded_by"] == "project":
            m["intensification_criterion"] = ""
    queue.write_table("moves", mrows, opened)
    assert any("without an intensification_criterion" in e for e in validate(opened, RAW_XLSX, RAW_MAVD))


def test_open_and_decide_end_to_end_in_a_git_checkout(tmp_path):
    """The CLI path: a clone, `open --no-push` makes a branch and a commit, `decide` makes a second commit."""
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(ROOT), str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(clone), "config", "user.name", "t"], check=True)
    for rel in ("pipeline/queue.py", "pipeline/templates/review.html"):   # the files under test, if not yet committed
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, clone / rel)
    run = clone / "harvest" / "runs" / "fixture"
    assert harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(run),
                         "--recordings", str(FIX / "recordings"), "--run-id", "fixture"]) == 0
    r = subprocess.run(["python", "-m", "pipeline.queue", "open", "--run", str(run), "--no-push"], cwd=clone, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert subprocess.run(["git", "-C", str(clone), "branch", "--show-current"], capture_output=True, text=True).stdout.strip() == "harvest/fixture"
    assert (clone / "docs/review/fixture.html").exists()
    log = subprocess.run(["git", "-C", str(clone), "log", "--oneline", "-1"], capture_output=True, text=True).stdout
    assert "Harvest fixture: 5 candidate events" in log
    eid = [e for e in rows(clone / "data", "events") if e["status"] == "candidate" and e["harvest_run_id"] == "fixture"][0]["event_id"]
    (clone / "decisions.json").write_text(json.dumps({"decisions": [{"event_id": eid, "action": "reject", "note": "test"}]}), encoding="utf-8")
    r = subprocess.run(["python", "-m", "pipeline.queue", "decide", "decisions.json", "--reviewer", "T", "--date", DATE], cwd=clone, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    log = subprocess.run(["git", "-C", str(clone), "log", "--oneline", "-2"], capture_output=True, text=True).stdout
    assert "Review by T: 1 rejected" in log
    assert validate(clone / "data", RAW_XLSX, RAW_MAVD) == []
