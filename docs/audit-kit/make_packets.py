"""Ticket 43, step 1: one packet per claimant-year of the project's records, as docs/audit-prompt.md asks."""
import csv, json, collections, sys
from pathlib import Path
sys.path.insert(0, "/home/claude/scs-developments-tracker")
from pipeline import schema
D = Path("/home/claude/scs-developments-tracker/data")
rd = lambda f: list(csv.DictReader(open(D / f, newline="", encoding="utf-8")))
M, E, S = rd("moves.csv"), rd("events.csv"), rd("sources.csv")
src = collections.defaultdict(list)
for s in S: src[s["event_id"]].append({k: s[k] for k in ("url", "title", "publisher", "pub_date", "language", "excerpt")})
evs_of = collections.defaultdict(list)
for e in E: evs_of[e["move_id"]].append(e)
W = {"declarative": 1, "demonstrative": 2, "coercive": 3, "force": 4}
def top(m): return max((t for t in schema.TYPE_FLAGS if m.get(t) == "1"), key=W.get, default="")
def issues(m): return {i for i in schema.ISSUE_FLAGS if m.get(i) == "1"}
def brief(m): return {"move_id": m["move_id"], "claimant": m["claimant"], "year": m["year"], "coded_by": m["coded_by"], "status": m["status"],
                      "type": [t for t in schema.TYPE_FLAGS if m.get(t) == "1"], "domains": [t for t in schema.DOMAIN_FLAGS if m.get(t) == "1"],
                      "issues": sorted(issues(m)), "subregions": [i + 1 for i, n in enumerate(schema.SUBREGION_FLAGS) if m.get(n) == "1"],
                      "dyads": m["dyads"], "ongoing_through": m["ongoing_through"], "intensification_criterion": m["intensification_criterion"],
                      "description": m["description"]}
def ev(e): return dict(e) | {"sources": src.get(e["event_id"], [])}
live = [m for m in M if m["status"] == "accepted"]
chubb = [m for m in live if m["coded_by"] == "chubb"]
proj = [m for m in live if m["coded_by"] == "project"]
dec = [e for e in E if e.get("extractor") and e["status"] in ("accepted", "rejected", "merged")]
keys = collections.defaultdict(lambda: {"moves": [], "events": []})
for m in proj: keys[(m["claimant"], m["year"])]["moves"].append(m)
for e in dec:
    y = (e["date_start"] or "")[:4] or "undated"
    keys[(e["claimant"], y)]["events"].append(e)
out = Path("/tmp/audit/packets"); n = 0; recs = 0
for (c, y), g in sorted(keys.items()):
    yi = int(y) if y.isdigit() else None
    moves = [brief(m) | {"events": [ev(e) for e in evs_of[m["move_id"]]]} for m in g["moves"]]
    seen = {e["event_id"] for m in g["moves"] for e in evs_of[m["move_id"]]}
    other = [ev(e) for e in g["events"] if e["event_id"] not in seen]   # accepted into moves of other years or Chubb's, rejected, merged
    for x in other:
        mv = next((m for m in M if m["move_id"] == x["move_id"]), None)
        if mv: x["its_move"] = brief(mv)
    ref = [brief(m) for m in live if m["claimant"] == c and yi and int(m["year"]) in (yi - 1, yi) and m["coded_by"] == "chubb" or
           (m["claimant"] == c and yi and int(m["year"]) in (yi - 1, yi) and m["coded_by"] == "project" and m not in g["moves"])]
    comp = []
    for m in g["moves"]:
        t, iss = top(m), issues(m)
        cands = [x for x in chubb if top(x) == t and issues(x) & iss and abs(int(x["year"]) - int(m["year"])) <= 5]
        if len(cands) < 4:   # Chubb stops in 2015: take the nearest years of the same type and issue
            cands = sorted([x for x in chubb if top(x) == t and issues(x) & iss], key=lambda x: abs(int(x["year"]) - int(m["year"])))[:8]
        comp += [brief(x) for x in cands[:12] if brief(x) not in comp]
    p = {"claimant": c, "year": y, "project_moves": moves, "other_events": other, "reference_moves_prev_and_same_year": ref,
         "chubb_comparison_set": comp[:30]}
    (out / f"{c}-{y}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    n += 1; recs += len(moves) + sum(len(m["events"]) for m in moves) + len(other)
print(n, "packets;", recs, "records")
