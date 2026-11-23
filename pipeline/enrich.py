"""Bring candidates up to the place rules agreed on 2026-11-23 (ticket 41), so every record reaches
review in the same, precise form:

- the place in English ("Huangyan Dao (Scarborough Shoal)" -> "Scarborough Shoal", ticket 32), with the
  source's wording kept in the review note;
- a named reef, shoal or island placed: its coordinates and sub-region from the gazetteer (as at intake,
  gazetteer.locate; the event's own coordinates, when it has them, always win);
- the sub-regions a place without a feature suggests ("off Sabah", "Block K", ticket 33) are not written
  here: they are a suggestion for the coder, computed when the record goes to Airtable.

Only candidates are touched (status "candidate"): an accepted or rejected event is the coder's. The step
is idempotent, and it runs at intake (pipeline.queue opens a run through it). To bring a run already
open up to date:

  python -m pipeline.enrich --data data --run CN-2021-2026      # rewrites that run's candidate rows
"""
from __future__ import annotations

import argparse
import re
import sys
from functools import lru_cache
from pathlib import Path

from pipeline import gazetteer

NOTE = "Source's wording for the place: “{}”."


TRANSLATIONS = gazetteer.GAZETTEER.parent / "place_translations.csv"


@lru_cache(maxsize=1)
def _translations() -> dict[str, str]:
    """Places the rules cannot put in English (whole Vietnamese phrases, administrative names), translated
    by hand: source wording -> English (data/reference/place_translations.csv)."""
    import csv
    if not TRANSLATIONS.exists():
        return {}
    return {r["source"]: r["english"] for r in csv.DictReader(open(TRANSLATIONS, encoding="utf-8"))}


def enrich(event: dict) -> dict:
    """The candidate in place, brought up to the rules; returns it."""
    name = (event.get("location_name") or "").strip()
    m = re.search(r"Source's wording for the place: “(.*?)”\.", event.get("review_note") or "")
    if m:   # already brought up once: start again from the source's words, so a better rule corrects it
        name = m.group(1)
    english = _translations().get(name) or (gazetteer.english_place(name) if name else name)
    if english != name and gazetteer.is_english_name(english):
        note = NOTE.format(name)
        if note not in (event.get("review_note") or ""):
            event["review_note"] = " ".join(x for x in ((event.get("review_note") or "").strip(), note) if x)
        event["location_name"] = english
    elif m:   # the better rule keeps the source's words: put them back and drop the note
        event["location_name"] = name
        event["review_note"] = re.sub(r"\s*" + re.escape(m.group(0)), "", event["review_note"]).strip()
    return gazetteer.locate(event)


def enrich_rows(rows: list[dict], run_id: str | None = None) -> int:
    """Enrich the candidate rows (of one run, if given); the number changed."""
    changed = 0
    for r in rows:
        if r.get("status") != "candidate" or (run_id and r.get("harvest_run_id") != run_id):
            continue
        before = dict(r)
        enrich(r)
        changed += r != before
    return changed


SEED_NOTE = "Place from the move's description (the features it names), added 2026-11-23."


def place_seed_events(events: list[dict], moves: list[dict], run_prefix: str = "seed") -> tuple[int, list[dict]]:
    """Chubb's dated incidents (the MAVD seed events) carry no place; give each the features its move's
    description names, in English. Coordinates and the sub-region only when the move names one feature and
    it lies in a sub-region the move is coded for; else the names alone. His coding is not changed. Returns
    (events changed, moves whose named features lie outside their coded sub-regions, for the maintainer)."""
    from pipeline import schema
    by_move = {m["move_id"]: m for m in moves}
    changed, outside = 0, {}
    for e in events:
        if not e.get("harvest_run_id", "").startswith(run_prefix) or e.get("location_name") or e.get("lat"):
            continue
        m = by_move.get(e.get("move_id"))
        if not m:
            continue
        feats = gazetteer.named_features(m["description"])
        if not feats:
            continue
        coded = {i + 1 for i, f in enumerate(schema.SUBREGION_FLAGS) if m.get(f) == "1"}
        srs = [int(f["subregion"] or gazetteer.subregion_of(f["lat"], f["lon"]) or 0) for f in feats]
        off = [(f["name_en"], sr) for f, sr in zip(feats, srs) if sr and sr not in coded]
        if off:
            outside[m["move_id"]] = {"move_id": m["move_id"], "coded": sorted(coded), "named": off, "description": m["description"]}
        e["location_name"] = "; ".join(f["name_en"] for f in feats)
        if len(feats) == 1 and srs[0] in coded:
            e["lat"], e["lon"] = f"{feats[0]['lat']:.5f}", f"{feats[0]['lon']:.5f}"
            e["subregion"], e["location_precision"] = str(srs[0]), "feature"
        e["review_note"] = " ".join(x for x in ((e.get("review_note") or "").strip(), SEED_NOTE) if x)
        changed += 1
    return changed, sorted(outside.values(), key=lambda r: r["move_id"])


def main(argv=None) -> int:
    from pipeline.queue import read_table, write_table
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--run", default=None, help="only this run's candidates (default: every candidate)")
    p.add_argument("--seed", action="store_true", help="also give Chubb's seed events their moves' places")
    a = p.parse_args(argv)
    events = read_table("events", a.data)
    n = enrich_rows(events, a.run)
    if a.seed:
        k, outside = place_seed_events(events, read_table("moves", a.data))
        print(f"{k} seed events placed; {len(outside)} of their moves name a feature outside their coded sub-regions")
    write_table("events", events, a.data)
    print(f"{a.data / 'events.csv'}: {n} candidate{'s' if n != 1 else ''} brought up to the place rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
