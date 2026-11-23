"""Ticket 41: candidates brought up to the place rules: the place in English with the source's wording
kept, and a named feature placed. Accepted and rejected events are the coder's and are left alone."""
from pipeline import enrich


def cand(**kw):
    row = {"event_id": "ev-x", "status": "candidate", "harvest_run_id": "R", "location_name": "", "lat": "", "lon": "",
           "location_precision": "feature", "subregion": "", "review_note": ""}
    row.update(kw)
    return row


def test_a_candidate_gets_its_place_in_english_and_on_the_map():
    r = enrich.enrich(cand(location_name="Huangyan Dao (Scarborough Shoal)"))
    assert r["location_name"] == "Scarborough Shoal"
    assert "Source's wording for the place: “Huangyan Dao (Scarborough Shoal)”." in r["review_note"]
    assert r["lat"] and r["lon"] and r["subregion"] == "4" and r["location_precision"] == "feature"
    again = enrich.enrich(dict(r))                 # idempotent: the note is not repeated
    assert again == r


def test_the_source_words_stay_where_they_are_english():
    r = enrich.enrich(cand(location_name="South China Sea (north of 12°N)"))
    assert r["location_name"] == "South China Sea (north of 12°N)" and r["review_note"] == ""


def test_only_candidates_of_the_run_are_touched():
    rows = [cand(location_name="Huangyan Dao (Scarborough Shoal)"),
            cand(event_id="ev-y", status="accepted", location_name="Huangyan Dao (Scarborough Shoal)"),
            cand(event_id="ev-z", harvest_run_id="other", location_name="Huangyan Dao (Scarborough Shoal)")]
    assert enrich.enrich_rows(rows, "R") == 1
    assert [r["location_name"] for r in rows] == ["Scarborough Shoal", "Huangyan Dao (Scarborough Shoal)", "Huangyan Dao (Scarborough Shoal)"]


def test_hand_translations_come_first():
    r = enrich.enrich(cand(location_name="Paracel (Hsisha) and Spratly (Nansha) islands"))
    assert r["location_name"] == "Paracel Islands and Spratly Islands"
    assert "Source's wording for the place: “Paracel (Hsisha) and Spratly (Nansha) islands”." in r["review_note"]


def test_every_candidate_place_on_record_reads_in_english():
    """The places of the candidates in the review runs (as recorded on 2026-11-23) all come out in English."""
    from pipeline import gazetteer
    for name in ["Huangyan Dao (Scarborough Shoal)", "Đá Hải Sâm and Đảo Ba Ba, Hoàng Sa (Paracel) Islands",
                 "Truong Sa island district and DK1 platforms", "Waters around Dongsha (Pratas) Island", "Ranai (Natuna)"]:
        out = enrich.enrich(cand(location_name=name))["location_name"]
        assert gazetteer.is_english_name(out), (name, out)
