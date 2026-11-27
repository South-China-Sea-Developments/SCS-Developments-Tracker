"""Episodes (ticket 45): runs of events by two claimants at the same place, proposed by the pipeline and
confirmed, named or rejected by the maintainer in Airtable.

An episode is found, not coded. Two accepted events are linked when they belong to claimants of a pair
whose moves are directed at each other (one move's dyads name the other claimant), lie within RADIUS_KM of
each other, and fall within GAP_DAYS of each other; an episode is a chain of such links (the connected
events), and must hold events by both claimants. Only events with coordinates and a day or month date
take part. An episode shows a sequence, never a claim that one act caused another.

data/episodes.csv holds the maintainer's decisions only:

    episode_id   ep- and ten hex characters, fixed when the episode is first proposed
    name         his name for it ("Second Thomas Shoal, 2023")
    claimants    the two claimant codes, space-separated, in name order ("CN PH")
    event_ids    the episode's events, space-separated, in date order
    status       confirmed | rejected
    reviewer, review_date, note

Proposals live in the base's Episodes table until he answers them. A proposal is `new` (no decided episode
shares an event with it) or `extend` (a decided episode, with events found since; the episode keeps its id
and, if confirmed, its name).

    python -m pipeline.episodes rows  --date YYYY-MM-DD --out batches.json [--data data]
    python -m pipeline.episodes apply --from export.json --date YYYY-MM-DD [--data data] [--out-dir DIR]
    python -m pipeline.episodes check [--data data]

`rows` finds the episodes, compares them with data/episodes.csv and writes the Airtable records to create
(batches of ten for the connector's create call), leaving out proposals already in the table (`--open`,
the table's exported rows). `apply` reads the table as exported, writes the decided rows to
data/episodes.csv, archives them under harvest/airtable/episodes/ and names the rows to clear. Neither
command calls Airtable.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path

from pipeline import schema
from pipeline.queue import read_table

RADIUS_KM = 25
GAP_DAYS = 180
COLUMNS = ["episode_id", "name", "claimants", "event_ids", "status", "reviewer", "review_date", "note"]
STATUSES = ["confirmed", "rejected"]
LETTER = {"CN": "C", "VN": "V", "PH": "P", "MY": "M", "BN": "B", "ID": "I", "TW": "R"}
CODE = {v: k for k, v in LETTER.items()}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CONFIG = Path(__file__).with_name("airtable.json")
FILE = "episodes.csv"


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


# ---- the decided episodes ----------------------------------------------------------------------------------
def read_episodes(data_dir: Path) -> list[dict]:
    p = Path(data_dir) / FILE
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_episodes(data_dir: Path, rows: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in sorted(rows, key=lambda r: r["episode_id"]):
        w.writerow({k: r.get(k, "") for k in COLUMNS})
    (Path(data_dir) / FILE).write_text(buf.getvalue(), encoding="utf-8")


# ---- finding them -------------------------------------------------------------------------------------------
def _targets(m: dict) -> set[str]:
    own = LETTER.get(m["claimant"], "")
    return {CODE[d[1]] for d in m.get("dyads", "").split() if len(d) == 2 and d[0] == own and d[1] in CODE and d[1] != own}


def _km(a: dict, b: dict) -> float:
    return 111.2 * math.hypot(a["lat"] - b["lat"], (a["lon"] - b["lon"]) * math.cos(math.radians((a["lat"] + b["lat"]) / 2)))


def placed_events(data_dir: Path) -> list[dict]:
    """The accepted events of accepted moves that can take part: coordinates and a day or month date."""
    moves = {m["move_id"]: m for m in read_table("moves", data_dir) if m["status"] == "accepted"}
    out = []
    for e in read_table("events", data_dir):
        m = moves.get(e["move_id"])
        if e["status"] != "accepted" or not m or not e["lat"] or not e["lon"] or e["date_precision"] not in ("day", "month"):
            continue
        try:
            day = dt.date.fromisoformat(e["date_start"])
        except ValueError:
            continue
        out.append({"id": e["event_id"], "move": e["move_id"], "c": m["claimant"], "to": _targets(m), "lat": float(e["lat"]),
                    "lon": float(e["lon"]), "day": day, "date": e["date_start"], "precision": e["date_precision"],
                    "place": e["location_name"], "summary": e["summary"]})
    return sorted(out, key=lambda p: (p["day"], p["id"]))


def find(data_dir: Path) -> list[dict]:
    """The episodes the data holds now: lists of event records, each episode in date order."""
    pts = placed_events(data_dir)
    links: dict[str, set[str]] = {p["id"]: set() for p in pts}
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            if (b["day"] - a["day"]).days > GAP_DAYS:
                break
            if a["c"] != b["c"] and (b["c"] in a["to"] or a["c"] in b["to"]) and _km(a, b) <= RADIUS_KM:
                links[a["id"]].add(b["id"])
                links[b["id"]].add(a["id"])
    by = {p["id"]: p for p in pts}
    seen: set[str] = set()
    out = []
    for p in pts:
        if p["id"] in seen or not links[p["id"]]:
            continue
        stack, comp = [p["id"]], set()
        while stack:
            x = stack.pop()
            if x not in comp:
                comp.add(x)
                stack.extend(links[x])
        seen |= comp
        evs = sorted((by[x] for x in comp), key=lambda q: (q["day"], q["id"]))
        if len({q["c"] for q in evs}) >= 2:
            out.append(evs)
    return out


def episode_id(evs: list[dict]) -> str:
    return "ep-" + hashlib.sha1(evs[0]["id"].encode()).hexdigest()[:10]


def proposed_name(evs: list[dict]) -> str:
    """Where and when, for the maintainer to edit: the place named most often (its first part), and the years."""
    places: dict[str, int] = {}
    for q in evs:
        first = re.split(r"[;(,]", q["place"] or "")[0].strip(" ,")
        first = re.sub(r"^(about|near|off|some)\s+[^A-Z]*", "", first).strip() or first
        if first:
            places[first] = places.get(first, 0) + 1
    place = max(places, key=lambda k: (places[k], -len(k))) if places else "Unplaced"
    y0, y1 = evs[0]["date"][:4], evs[-1]["date"][:4]
    return f"{place}, {y0}" if y0 == y1 else f"{place}, {y0}–{y1[2:] if y0[:2] == y1[:2] else y1}"


def span(evs: list[dict]) -> str:
    a, b = evs[0]["date"], evs[-1]["date"]
    ma, mb = MONTHS[int(a[5:7]) - 1], MONTHS[int(b[5:7]) - 1]
    if a[:7] == b[:7]:
        return f"{ma} {a[:4]}"
    return f"{ma}–{mb} {a[:4]}" if a[:4] == b[:4] else f"{ma} {a[:4]} – {mb} {b[:4]}"


def proposals(data_dir: Path) -> list[dict]:
    """What to put to the maintainer: every episode found that is new, or that adds events to one he decided."""
    decided = read_episodes(data_dir)
    owner = {eid: d for d in decided for eid in d["event_ids"].split()}
    names = {c["code"]: c["name"] for c in read_table("claimants", data_dir)}
    dates = {e["event_id"]: e["date_start"] for e in read_table("events", data_dir)}
    out = []
    for evs in find(data_dir):
        ids = [q["id"] for q in evs]
        hit = next((owner[i] for i in ids if i in owner), None)
        if hit and set(ids) <= set(hit["event_ids"].split()):
            continue   # nothing new since he decided it
        pair = sorted({q["c"] for q in evs}, key=lambda c: names.get(c, c))
        old = hit["event_ids"].split() if hit else []
        new_ids = [i for i in ids if i not in old]
        every = sorted(set(ids) | set(old), key=lambda i: (dates.get(i, ""), i))
        out.append({"episode_id": hit["episode_id"] if hit else episode_id(evs), "kind": "extend" if hit else "new",
                    "was": hit["status"] if hit else "", "name": hit["name"] if hit and hit["name"] else proposed_name(evs),
                    "claimants": " ".join(pair), "pair": " and ".join(names.get(c, c) for c in pair), "span": span(evs),
                    "event_ids": " ".join(every), "new_events": " ".join(new_ids), "n": len(every),
                    "lines": "\n".join(f"{q['date']} · {names.get(q['c'], q['c'])} · {q['move']} · {q['summary'][:140]}" for q in evs)})
    return out


# ---- Airtable rows ------------------------------------------------------------------------------------------
def rows(data_dir: Path, date: str, open_ids: set[str] | None = None) -> list[dict]:
    """The records to create in the Episodes table, keyed by field id, leaving out those already open there."""
    f = load_config().get("episodes", {}).get("field_ids", {})
    out = []
    for p in proposals(data_dir):
        if open_ids and p["episode_id"] in open_ids:
            continue
        rec = {"episode": p["episode_id"], "kind": p["kind"], "proposed_name": p["name"], "name": p["name"], "pair": p["pair"],
               "claimants": p["claimants"], "span": p["span"], "n_events": p["n"], "events": p["lines"], "event_ids": p["event_ids"],
               "new_events": p["new_events"] if p["kind"] == "extend" else "", "previously": p["was"], "proposed": date, "decision": "undecided"}
        out.append({f.get(k, k): v for k, v in rec.items()})
    return out


def _plain(v):
    if isinstance(v, dict):
        return v.get("name", "")
    if isinstance(v, list):
        return ", ".join(_plain(x) for x in v)
    return "" if v is None else str(v)


def apply(export: list[dict], data_dir: Path, date: str, reviewer: str = "maintainer", out_dir: Path | None = None) -> dict:
    """Write the decided rows of an exported Episodes table into data/episodes.csv. Returns what was applied,
    what was refused (with why) and the record ids to clear from the table."""
    f = {v: k for k, v in load_config().get("episodes", {}).get("field_ids", {}).items()}
    known = {e["event_id"]: e for e in read_table("events", data_dir)}
    decided = {d["episode_id"]: d for d in read_episodes(data_dir)}
    applied, refused, clear = [], [], []
    for rec in export:
        cells = rec.get("cellValuesByFieldId") or rec.get("fields") or {}
        r = {f.get(k, k): _plain(v) for k, v in cells.items()}
        dec = (r.get("decision") or "undecided").strip().lower()
        if dec not in ("confirm", "reject"):
            continue
        eid = r.get("episode", "").strip()
        ids = r.get("event_ids", "").split()
        bad = [i for i in ids if i not in known or known[i]["status"] != "accepted"]
        if not re.fullmatch(r"ep-[0-9a-f]{10}", eid) or not ids or bad:
            refused.append({"record": rec.get("id"), "episode": eid, "why": f"events not accepted or unknown: {' '.join(bad)}" if bad else "no episode id or events"})
            continue
        name = (r.get("name") or r.get("proposed_name") or "").strip()
        decided[eid] = {"episode_id": eid, "name": name, "claimants": r.get("claimants", "").strip(), "event_ids": " ".join(ids),
                        "status": "confirmed" if dec == "confirm" else "rejected", "reviewer": reviewer, "review_date": date,
                        "note": (r.get("note") or "").strip()}
        applied.append({"record": rec.get("id"), "episode": eid, "status": decided[eid]["status"], "name": name})
        clear.append(rec.get("id"))
    if applied:
        write_episodes(data_dir, list(decided.values()))
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{date}.json").write_text(json.dumps({"date": date, "applied": applied, "rows": export}, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"applied": applied, "refused": refused, "clear": [c for c in clear if c]}


# ---- checking the file --------------------------------------------------------------------------------------
def check(data_dir: Path) -> list[str]:
    """Errors in data/episodes.csv: shape, ids, events that are not accepted, claimants that do not match."""
    p = Path(data_dir) / FILE
    if not p.exists():
        return []
    errs = []
    with p.open(encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        if rd.fieldnames != COLUMNS:
            return [f"{FILE}: columns {rd.fieldnames} != {COLUMNS}"]
        recs = list(rd)
    events = {e["event_id"]: e for e in read_table("events", data_dir)}
    moves = {m["move_id"]: m for m in read_table("moves", data_dir)}
    seen_ids, owner = set(), {}
    for r in recs:
        eid = r["episode_id"]
        where = f"{FILE} {eid or '?'}"
        if not re.fullmatch(r"ep-[0-9a-f]{10}", eid):
            errs.append(f"{where}: bad episode_id")
        if eid in seen_ids:
            errs.append(f"{where}: listed twice")
        seen_ids.add(eid)
        if r["status"] not in STATUSES:
            errs.append(f"{where}: status {r['status']!r} not in {STATUSES}")
        if r["status"] == "confirmed" and not r["name"].strip():
            errs.append(f"{where}: a confirmed episode needs a name")
        pair = r["claimants"].split()
        if len(pair) != 2 or any(c not in schema.CLAIMANT_CODES for c in pair):
            errs.append(f"{where}: claimants {r['claimants']!r} is not two claimant codes")
        ids = r["event_ids"].split()
        if not ids:
            errs.append(f"{where}: no events")
        for i in ids:
            e = events.get(i)
            if not e:
                errs.append(f"{where}: unknown event {i}")
            elif r["status"] == "confirmed" and (e["status"] != "accepted" or moves.get(e["move_id"], {}).get("status") != "accepted"):
                errs.append(f"{where}: event {i} is no longer accepted")
            elif len(pair) == 2 and moves.get(e["move_id"], {}).get("claimant") not in pair:
                errs.append(f"{where}: event {i} is by a claimant outside {r['claimants']}")
            if i in owner and owner[i] != eid and r["status"] == "confirmed":
                errs.append(f"{where}: event {i} is also in {owner[i]}")
            owner[i] = eid
    return errs


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rows")
    r.add_argument("--date", required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--open", type=Path, default=None, help="the Episodes table as exported, to leave out proposals already open")
    r.add_argument("--data", type=Path, default=Path("data"))
    a_ = sub.add_parser("apply")
    a_.add_argument("--from", dest="src", type=Path, required=True)
    a_.add_argument("--date", required=True)
    a_.add_argument("--data", type=Path, default=Path("data"))
    a_.add_argument("--out-dir", type=Path, default=Path("harvest/airtable/episodes"))
    a_.add_argument("--reviewer", default="maintainer")
    c = sub.add_parser("check")
    c.add_argument("--data", type=Path, default=Path("data"))
    a = p.parse_args(argv)
    if a.cmd == "rows":
        open_ids = set()
        if a.open:
            f = load_config().get("episodes", {}).get("field_ids", {}).get("episode", "episode")
            for rec in json.loads(a.open.read_text(encoding="utf-8")).get("records", []):
                cells = rec.get("cellValuesByFieldId") or rec.get("fields") or {}
                open_ids.add(_plain(cells.get(f, "")))
        recs = rows(a.data, a.date, open_ids)
        a.out.write_text(json.dumps([recs[i:i + 10] for i in range(0, len(recs), 10)], indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{len(recs)} proposal(s) in {(len(recs) + 9) // 10} batch(es) -> {a.out}")
        return 0
    if a.cmd == "apply":
        doc = json.loads(a.src.read_text(encoding="utf-8"))
        res = apply(doc.get("records", doc) if isinstance(doc, dict) else doc, a.data, a.date, a.reviewer, a.out_dir)
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 1 if res["refused"] else 0
    errs = check(a.data)
    for e in errs:
        print(e)
    print(f"{'FAIL' if errs else 'OK'}: {len(errs)} error(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
