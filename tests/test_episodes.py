"""Ticket 45: episodes found in the events, put to the maintainer, applied to data/episodes.csv, checked."""
import csv
import shutil

import pytest

from pipeline import episodes
from pipeline.queue import read_table
from pipeline.validate import validate
from tests.conftest import DATA_DIR


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    shutil.copytree(DATA_DIR, d, ignore=shutil.ignore_patterns("raw"))
    (d / episodes.FILE).unlink(missing_ok=True)
    return d


def _export(props, decisions):
    """The Episodes table as the connector exports it, keyed by field id, with the maintainer's answers."""
    f = episodes.load_config()["episodes"]["field_ids"]
    out = []
    for i, p in enumerate(props):
        dec, name = decisions.get(p["episode_id"], ("undecided", ""))
        out.append({"id": f"rec{i:014d}", "cellValuesByFieldId": {
            f["episode"]: p["episode_id"], f["decision"]: {"name": dec}, f["name"]: name or p["name"],
            f["proposed_name"]: p["name"], f["claimants"]: p["claimants"], f["event_ids"]: p["event_ids"]}})
    return out


def test_episodes_hold_two_claimants_at_one_place_within_six_months(data):
    found = episodes.find(data)
    assert found, "the live data holds episodes"
    for evs in found:
        assert len({q["c"] for q in evs}) == 2
        days = [q["day"] for q in evs]
        assert days == sorted(days)
        # every event has a partner by the other claimant within the radius and the gap
        for q in evs:
            assert any(r["c"] != q["c"] and abs((r["day"] - q["day"]).days) <= episodes.GAP_DAYS
                       and episodes._km(q, r) <= episodes.RADIUS_KM for r in evs), q["id"]
    ids = [q["id"] for evs in found for q in evs]
    assert len(ids) == len(set(ids)), "an event is in one episode at most"


def test_proposals_are_stable_and_named_by_place_and_years(data):
    a, b = episodes.proposals(data), episodes.proposals(data)
    assert [p["episode_id"] for p in a] == [p["episode_id"] for p in b]
    assert all(p["kind"] == "new" and p["episode_id"].startswith("ep-") for p in a)
    assert all(p["name"].rsplit(", ", 1)[-1][:4].isdigit() for p in a)
    rows = episodes.rows(data, "2026-11-27")
    f = episodes.load_config()["episodes"]["field_ids"]
    assert len(rows) == len(a) and all(r[f["decision"]] == "undecided" and r[f["new_events"]] == "" for r in rows)
    assert episodes.rows(data, "2026-11-27", open_ids={a[0]["episode_id"]})[0][f["episode"]] != a[0]["episode_id"]


def test_apply_writes_the_answers_and_the_next_proposals_skip_them(data, tmp_path):
    props = episodes.proposals(data)
    keep, drop = props[0], props[1]
    res = episodes.apply(_export(props, {keep["episode_id"]: ("confirm", "My name"), drop["episode_id"]: ("reject", "")}),
                         data, "2026-11-28", out_dir=tmp_path / "arch")
    assert {a["status"] for a in res["applied"]} == {"confirmed", "rejected"} and not res["refused"] and len(res["clear"]) == 2
    rows = {r["episode_id"]: r for r in episodes.read_episodes(data)}
    assert rows[keep["episode_id"]]["name"] == "My name" and rows[drop["episode_id"]]["status"] == "rejected"
    assert (tmp_path / "arch" / "2026-11-28.json").exists()
    assert episodes.check(data) == []
    left = {p["episode_id"] for p in episodes.proposals(data)}
    assert keep["episode_id"] not in left and drop["episode_id"] not in left


def test_an_episode_with_events_found_since_comes_back_as_an_extension(data):
    props = episodes.proposals(data)
    big = max(props, key=lambda p: p["n"])
    ids = big["event_ids"].split()
    big_short = dict(big, event_ids=" ".join(ids[:-1]))
    episodes.apply(_export([big_short], {big["episode_id"]: ("confirm", "Named")}), data, "2026-11-28")
    again = next(p for p in episodes.proposals(data) if p["episode_id"] == big["episode_id"])
    assert again["kind"] == "extend" and again["was"] == "confirmed" and again["name"] == "Named"
    assert again["new_events"] == ids[-1] and again["n"] == len(ids)


def test_check_catches_a_broken_file(data):
    ev = next(e for e in read_table("events", data) if e["status"] == "accepted")
    with (data / episodes.FILE).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=episodes.COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerow({"episode_id": "ep-0000000000", "name": "", "claimants": "CN PH", "event_ids": "ev-nope", "status": "confirmed"})
        w.writerow({"episode_id": "bad", "name": "x", "claimants": "CN", "event_ids": ev["event_id"], "status": "maybe"})
    errs = "\n".join(episodes.check(data))
    for bit in ("needs a name", "unknown event ev-nope", "bad episode_id", "status 'maybe'", "is not two claimant codes"):
        assert bit in errs, bit
    assert any("CODE: episodes.csv" in e for e in validate(data, None))


def test_the_live_data_validates_with_its_episodes():
    assert episodes.check(DATA_DIR) == []
