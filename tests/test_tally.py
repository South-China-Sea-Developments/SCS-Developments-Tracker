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


def test_report_counts_every_candidate_once_and_carries_the_warning(tmp_path):
    rows = tally.load_candidates(ROOT)
    n_manual = sum(len(json.loads(p.read_text(encoding="utf-8"))) for p in (ROOT / "harvest" / "manual").glob("*.json"))
    assert len(rows) >= 1000 and len(rows) <= n_manual + 200           # the sets, plus weekly rows not in a set
    t = tally.tallies(rows)
    assert sum(sum(c.values()) for yrs in t.values() for c in yrs.values()) == sum(1 for r in rows if r["year"].isdigit())
    md = tally.report(rows, today="2026-11-20")
    assert "not of what happened" in md and "never a number to cite" in md and "## CN" in md and "| 2016 |" in md
    out = tmp_path / "t.md"
    assert tally.main(["--out", str(out), "--date", "2026-11-20"]) == 0 and out.read_text(encoding="utf-8") == md + "\n"


def test_chubbs_increase_worded_moves_are_listed_with_their_cited_sources():
    with open(DATA_DIR / "moves.csv", newline="", encoding="utf-8") as f:
        moves = list(csv.DictReader(f))
    items = tally.chubb_increases(moves)
    ids = {i["move_id"]: i for i in items}
    assert "CN200802" in ids and "CN201302" in ids and all(i["claimant"] in ("CN", "VN", "PH") for i in items)
    assert any("Lan jiang weishi" in s for s in ids["CN200801"]["sources"])
    md = tally.increases_markdown(items)
    assert md.startswith("### CN") and "`CN200802`" in md
