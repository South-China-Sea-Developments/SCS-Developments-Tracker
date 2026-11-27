"""Ticket 33: sub-regions suggested from what a candidate says about its place."""
import csv

from pipeline import places


def subs(location, summary=""):
    return [s["subregion"] for s in places.suggest_subregions({"location_name": location, "summary": summary})]


def test_areas_that_are_not_features():
    assert subs("Malaysian continental shelf off Sabah and Sarawak, near the West Capella drillship") == [10, 7]
    assert subs("Block SC 75, west of Palawan")[0] == 6
    assert subs("waters outside the mouth of the Gulf of Tonkin (Beibu Gulf)") == [1]
    assert subs("North Natuna Sea (Indonesian EEZ)") == [10]
    assert subs("Ayungin (Second Thomas) Shoal") == [6]


def test_coordinates_win_and_an_eez_only_counts_alone():
    assert places.suggest_subregions({"lat": "9.73", "lon": "115.87", "location_name": "off Sarawak"})[0]["basis"] == "its coordinates"
    assert subs("Bruneian EEZ") == [8, 10, 7]                    # broad, but the only clue
    assert subs("Louisa Reef in the Bruneian EEZ") == [7]          # the reef is narrower: the EEZ is dropped


def test_the_summary_only_when_the_place_says_nothing():
    assert subs("disputed waters", "Chinese ships blocked a resupply mission to Second Thomas Shoal") == [6]
    assert subs("nowhere in particular") == []


# Events whose place text points the suggester elsewhere, where the coder's sub-region stands (ADR 0003).
# Listed by name, so that any new disagreement still fails and gets looked at.
CODER_OVERRIDES = {
    "ev-d1c89a64f7": "Block ND2 (Lala-1), 'beyond 200 nm off Sabah' but in the Malaysia-Viet Nam Defined Area: coded 9 (2026-11-27)",
    "ev-cae2a725dd": "Blocks ND1/ND2, the West Capella drilling site, 'off Sabah': coded 9 (2026-11-27)",
}


def test_agrees_with_the_coded_sub_regions():
    """On the accepted events whose sub-region is known (no coordinates given), the suggestion is never
    wrong about the place: the right sub-region is first in at least 85%, and what the place text alone
    suggests always lists it or is empty. A place named only in the summary (a sovereignty claim such as
    "over Hoang Sa and Truong Sa") is a hint, not the act's place: the coder's sub-region stands
    (ev-5f77c68ada, Vietnam's central-area shelf submission, coded 3 while its summary names the Paracels).
    Events whose place text itself misleads the suggester are listed in CODER_OVERRIDES."""
    from pathlib import Path
    rows = [e for e in csv.DictReader(open(Path(__file__).parents[1] / "data/events.csv", encoding="utf-8")) if e["subregion"] and e["status"] == "accepted"]
    top = wrong = 0
    for e in rows:
        got = subs(e["location_name"], e["summary"])
        top += bool(got) and got[0] == int(e["subregion"])
        own = subs(e["location_name"])
        wrong += bool(own) and int(e["subregion"]) not in own and e["event_id"] not in CODER_OVERRIDES
    assert wrong == 0 and top >= 0.85 * len(rows), (top, wrong, len(rows))


def test_note_reads_for_the_coder():
    n = places.note(places.suggest_subregions({"location_name": "off Sabah"}))
    assert n.startswith("Sub-regions suggested: 7 Spratly SE (Sabah coast 85%)")
