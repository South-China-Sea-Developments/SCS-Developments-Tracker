"""Ticket 27: the assertiveness map's measure — type-weighted moves per sub-region in a five-year window."""
from pipeline import schema
from web.build import window_scores


def move(mid, claimant, year, types, subregions, status="accepted"):
    m = {"move_id": mid, "claimant": claimant, "year": str(year), "status": status}
    for t in schema.TYPE_FLAGS:
        m[t] = "1" if t in types else "0"
    for i, f in enumerate(schema.SUBREGION_FLAGS, 1):
        m[f] = "1" if i in subregions else "0"
    return m


MOVES = [
    move("CN200001", "CN", 2000, ["declarative"], [2]),
    move("CN200301", "CN", 2003, ["demonstrative", "coercive"], [2, 5]),   # weighs by its highest type: 3
    move("VN200401", "VN", 2004, ["force"], [5]),
    move("PH199901", "PH", 1999, ["coercive"], [6]),                        # outside 2000–2004
    move("CN200402", "CN", 2004, ["force"], [7], status="pending"),        # not published, not counted
]


def test_scores_sum_the_highest_type_per_subregion_in_the_window():
    w = window_scores(MOVES, first=1995, last=2004)
    assert w["span"] == 5 and w["ends"][0] == 1999 and w["ends"][-1] == 2004
    s = w["scores"]["ALL"]["2004"]   # 2000–2004
    assert s[1] == 1 + 3 and s[4] == 3 + 4 and s[5] == 0 and s[6] == 0
    assert len(s) == 10


def test_a_claimant_sees_only_its_own_moves():
    w = window_scores(MOVES, first=1995, last=2004)
    assert w["scores"]["CN"]["2004"][4] == 3 and w["scores"]["VN"]["2004"][4] == 4
    assert w["scores"]["PH"]["2003"][5] == 3 and w["scores"]["PH"]["2004"][5] == 0   # 1999 falls out of 2000–2004
    assert set(w["scores"]) == {"ALL", *schema.CLAIMANT_CODES}


def test_the_scale_is_fixed_across_windows_per_selection():
    w = window_scores(MOVES, first=1995, last=2004)
    assert w["max"]["ALL"] == max(max(v) for v in w["scores"]["ALL"].values()) == 7
    assert w["max"]["VN"] == 4 and w["max"]["MY"] == 0


def test_the_latest_window_ends_at_the_year_given_even_with_no_moves_in_it():
    w = window_scores(MOVES, first=1995, last=2026)
    assert w["ends"][-1] == 2026 and w["scores"]["ALL"]["2026"] == [0] * 10
