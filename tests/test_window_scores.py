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


def test_moves_carry_the_features_they_name_and_the_map_gets_their_positions():
    from web.build import window_moves
    m = move("CN201201", "CN", 2012, ["coercive"], [4])
    m["description"] = "2012: Standoff at Scarborough Shoal; patrols near Mischief Reef."
    m["dyads"] = "CP CV"
    feats = {}
    [w] = window_moves([m], feats)
    assert w["f"] == ["scarborough-shoal", "mischief-reef"] and w["w"] == 3 and w["g"] == ["P", "V"]
    assert set(feats) == {"scarborough-shoal", "mischief-reef"} and 14 < feats["scarborough-shoal"]["lat"] < 16


def test_moves_are_also_placed_by_their_events():
    """Ticket 34: a move whose description names no reef is placed by its accepted events' places and by
    a position the coder gave the event; a rejected event places nothing."""
    from web.build import window_moves
    m = move("CN202101", "CN", 2021, ["demonstrative"], [10])
    m["description"] = "2021: A Chinese survey ship works off Malaysia."
    m["dyads"] = "CM"
    evs = [{"event_id": "ev-a", "status": "accepted", "location_name": "Luconia Breakers", "lat": "", "lon": ""},
           {"event_id": "ev-b", "status": "accepted", "location_name": "Block K off Sabah", "lat": "6.075", "lon": "114.343"},
           {"event_id": "ev-c", "status": "rejected", "location_name": "Scarborough Shoal", "lat": "", "lon": ""}]
    feats = {}
    [w] = window_moves([m], feats, {"CN202101": evs})
    assert w["f"] == ["luconia-breakers", "ev:ev-b"]
    assert feats["ev:ev-b"] == {"n": "Block K off Sabah", "lat": 6.075, "lon": 114.343, "sr": 7}


def test_one_word_names_of_single_features():
    from pipeline.gazetteer import named_features
    assert [f["name_en"] for f in named_features("2012 June: Philippines opens school on Thitu/Pagasa.")] == ["Thitu Island"]


def test_every_subregion_label_sits_inside_its_polygon():
    import json
    from pipeline.gazetteer import SUBREGIONS, subregion_of
    from web.build import slim_geojson
    gj = slim_geojson(json.loads(SUBREGIONS.read_text(encoding="utf-8")))
    for f in gj["features"]:
        lon, lat = f["properties"]["lab"]
        assert subregion_of(lat, lon) == f["properties"]["n"], f["properties"]["name"]


def test_shared_weights_split_a_move_among_its_subregions():
    w = window_scores(MOVES, first=1995, last=2004, shared=True)
    s = w["scores"]["ALL"]["2004"]
    # CN200001 (1, one sub-region) + CN200301 (3 over two) on 2; CN200301's half + VN200401 (4, one) on 5
    assert s[1] == 1 + 1.5 and s[4] == 1.5 + 4
    assert w["max"]["ALL"] == 5.5
