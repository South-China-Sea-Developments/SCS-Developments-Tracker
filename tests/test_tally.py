"""Ticket 25: candidate tallies by practice, a pointer to frequency sources."""
import csv
import json

from pipeline import tally
from tests.conftest import DATA_DIR, ROOT


def test_practice_is_read_off_the_summary_by_the_first_matching_rule():
    cases = {
        "Two Chinese vessels rammed and sank the Quang Ngai fishing boat QNg 90479": "sinking/ramming",
        "China Coast Guard ships chased Filipino fishermen away from Scarborough Shoal": "fisher enforcement",
        "PLAN ships shadowed and warned off the USS Decatur near the Paracels": "interception (air/sea)",
        "The PLA held live-fire drills around the Paracels": "exercise/drill",
        "The China Coast Guard said it had intensified law-enforcement patrols in the territorial waters": "patrol/presence",
        "Vietnam's spokesperson protested China's construction on Fiery Cross Reef": "diplomatic statement",
        "Indonesia licensed a new exploration block, Arwana III, south of the Tuna block": "energy/survey",
        "Hainan province passed regulations authorising board-and-search of foreign boats": "legislation/administration",
        "President Ma visited Taiping Island with the defence minister": "occupation/landing",
        "Dredgers began reclamation at Mischief Reef": "construction/reclamation",
        "Foreign Secretary Yasay said the Philippines would not deviate from the ruling": "other",
    }
    for summary, want in cases.items():
        assert tally.practice(summary) == want, summary


def _root(tmp_path):
    """A small repository root: two compiled sets and an events.csv with one harvested row that is also
    in a set (counted once) and one that is not (counted)."""
    root = tmp_path / "repo"
    (root / "harvest" / "manual").mkdir(parents=True)
    (root / "data").mkdir()
    sets = {
        "20261107-CN-2016-2020.json": [
            {"claimant": "CN", "date_start": "2016-07-09", "summary": "Two Chinese vessels rammed and sank the fishing boat QNg 90479"},
            {"claimant": "CN", "date_start": "2016-07-09", "summary": "Two Chinese vessels rammed and sank the fishing boat QNg 90479 near Woody"},   # a near-twin: distinct
            {"claimant": "CN", "date_start": "2016-01-02", "summary": "China flew a civil aircraft to the runway on Fiery Cross Reef"},
        ],
        "20261107-VN-2016-2020.json": [
            {"claimant": "VN", "date_start": "2017-03-01", "summary": "Vietnam's spokesperson protested China's cruise to the Paracels"},
        ],
    }
    for name, rows in sets.items():
        (root / "harvest" / "manual" / name).write_text(json.dumps(rows), encoding="utf-8")
    cols = ["event_id", "claimant", "date_start", "summary", "harvest_run_id", "status"]
    with open(root / "data" / "events.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerow({"event_id": "ev-1", "claimant": "VN", "date_start": "2017-03-01", "summary": "Vietnam's spokesperson protested China's cruise to the Paracels", "harvest_run_id": "VN-2016-2020", "status": "candidate"})
        w.writerow({"event_id": "ev-2", "claimant": "PH", "date_start": "2026-10-04", "summary": "China Coast Guard ships chased Filipino fishermen from Scarborough", "harvest_run_id": "weekly-2026-10-06", "status": "rejected"})
        w.writerow({"event_id": "s-1", "claimant": "PH", "date_start": "1995-01-01", "summary": "seed row", "harvest_run_id": "seed-mats", "status": "accepted"})
    return root


def test_report_counts_every_candidate_once_and_carries_the_warning(tmp_path):
    root = _root(tmp_path)
    rows = tally.load_candidates(root)
    assert len(rows) == 5                                   # 4 in the sets + the weekly row; the shared VN row once; no seed row
    t = tally.tallies(rows)
    assert t["CN"]["2016"]["sinking/ramming"] == 2 and t["CN"]["2016"]["construction/reclamation"] == 1 and t["PH"]["2026"]["fisher enforcement"] == 1
    md = tally.report(rows, today="2026-11-20")
    assert "not of what happened" in md and "never a number to cite" in md and "## CN" in md and "| 2016 | 2 |" in md
    out = tmp_path / "t.md"
    assert tally.main(["--root", str(root), "--out", str(out), "--date", "2026-11-20"]) == 0
    assert out.read_text(encoding="utf-8") == md + "\n"
    # the live repository tallies without error and holds the backfill
    live = tally.load_candidates(ROOT)
    assert len(live) >= 1000 and "## CN" in tally.report(live)


def test_citations_are_balanced_parentheses_without_amounts():
    d = 'Patrols increase (SOA, ZGHYNJ 2008, 127; CCTV, "Lan jiang weishi"); subsidy (S$3,400) rose (Zhang, "A (b), c") in (2008).'
    assert tally._citations(d) == ['SOA, ZGHYNJ 2008, 127; CCTV, "Lan jiang weishi"', 'Zhang, "A (b), c"']


def test_the_generated_section_is_refreshed_in_place_and_never_corrupts_the_note(tmp_path, capsys):
    note = tmp_path / "n.md"
    note.write_text("head\n<!-- generated: start -->\nold\n<!-- generated: end -->\ntail\n", encoding="utf-8")
    assert tally.refresh_generated(note, "new <!-- generated: end --> text") == 0
    assert note.read_text(encoding="utf-8") == "head\n<!-- generated: start -->\nnew  text\n<!-- generated: end -->\ntail\n"
    note.write_text("no markers here\n", encoding="utf-8")
    assert tally.refresh_generated(note, "x") == 2 and note.read_text(encoding="utf-8") == "no markers here\n"
    assert "x" in capsys.readouterr().out
    assert tally.refresh_generated(tmp_path / "missing.md", "y") == 0


def test_chubbs_increase_worded_moves_are_listed_with_their_cited_sources():
    with open(DATA_DIR / "moves.csv", newline="", encoding="utf-8") as f:
        moves = list(csv.DictReader(f))
    items = tally.chubb_increases(moves)
    ids = {i["move_id"]: i for i in items}
    assert "CN200802" in ids and "CN201302" in ids and all(i["claimant"] in ("CN", "VN", "PH") for i in items)
    assert any("Lan jiang weishi" in s for s in ids["CN200801"]["sources"])
    md = tally.increases_markdown(items)
    assert md.startswith("### CN") and "`CN200802`" in md
