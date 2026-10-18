"""The agreement report: how often the machine's suggested coding matched the coder's final coding.

Because suggestions stay on the event rows (ADR 0003) and the final coding lives on the move, the
report is derived, never stored: the site build writes data/agreement.json and the methodology page
renders it; this module also prints it as Markdown.

What is compared. A "compared" event is an accepted event that carries a suggestion (an extractor
and a suggested Type) and belongs to an accepted move: its suggested Type, Domains, Issues and
dyads against the move's. Agreement on a set (Domains, Issues, dyads) is exact set equality.
"Grouping" compares what the machine said about which move the event belongs to: a suggested
move_id agrees when it is the move the coder chose; no suggestion (a new move) agrees when the
coder formed a new move with it (the move's coding date is the event's review date). A "decided"
event is any accepted, merged (duplicate) or rejected event with a suggestion; the outcome counts
show how many suggestions became dataset content. Period = the event's year; extractor version =
the model and prompt hash recorded on the event. MATS-era seed events carry no suggestion and are
never counted.

Usage: python -m pipeline.agreement [--data DIR] [--json]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from pipeline import schema

ROOT = Path(__file__).resolve().parent.parent
DIMENSIONS = ("type", "domains", "issues", "dyads", "grouping", "all_three")
OUTCOMES = ("accepted", "merged", "rejected")


def _flags(m: dict, flags: list[str]) -> set[str]:
    return {f for f in flags if m.get(f) == "1"}


def _new_cell() -> dict:
    return {"n": 0, **{d: {"agree": 0, "n": 0} for d in DIMENSIONS}, "outcome": {o: 0 for o in OUTCOMES}}


def compare(e: dict, m: dict) -> dict:
    """Per-dimension agreement for one compared event and its move."""
    s_type = e["suggested_type"]
    f_types = _flags(m, schema.TYPE_FLAGS)
    s_dom, f_dom = set(e["suggested_domains"].split()), _flags(m, schema.DOMAIN_FLAGS)
    s_iss, f_iss = set(e["suggested_issues"].split()), _flags(m, schema.ISSUE_FLAGS)
    s_dy, f_dy = set(e["suggested_dyads"].split()), set(m["dyads"].split())
    if e["suggested_move_id"]:
        grouping = e["suggested_move_id"] == m["move_id"]
    else:
        grouping = m["coded_by"] == "project" and m["coding_date"] == e["review_date"]
    out = {"type": f_types == {s_type}, "domains": s_dom == f_dom, "issues": s_iss == f_iss, "dyads": s_dy == f_dy, "grouping": grouping}
    out["all_three"] = out["type"] and out["domains"] and out["issues"]
    return out


def report(events: list[dict], moves: list[dict]) -> dict:
    moves_by_id = {m["move_id"]: m for m in moves if m["status"] == "accepted"}
    decided = [e for e in events if e["extractor"] and e["suggested_type"] and e["status"] in OUTCOMES]
    compared = [e for e in decided if e["status"] == "accepted" and e["move_id"] in moves_by_id]
    totals, by_ext, by_period = _new_cell(), {}, {}
    confusion = {t: Counter() for t in schema.TYPE_FLAGS}
    flags = {"domains": {f: {"suggested": 0, "final": 0, "both": 0} for f in schema.DOMAIN_FLAGS},
             "issues": {f: {"suggested": 0, "final": 0, "both": 0} for f in schema.ISSUE_FLAGS}}
    for e in decided:
        cells = [totals, by_ext.setdefault(e["extractor"], _new_cell()), by_period.setdefault(e["date_start"][:4] or "undated", _new_cell())]
        for c in cells:
            c["outcome"][e["status"]] += 1
        if e not in compared:
            continue
        m = moves_by_id[e["move_id"]]
        res = compare(e, m)
        for c in cells:
            c["n"] += 1
            for d in DIMENSIONS:
                c[d]["n"] += 1
                c[d]["agree"] += int(res[d])
        final_types = _flags(m, schema.TYPE_FLAGS)
        if e["suggested_type"] in confusion and final_types:
            confusion[e["suggested_type"]][sorted(final_types)[0]] += 1
        for dim, flist in (("domains", schema.DOMAIN_FLAGS), ("issues", schema.ISSUE_FLAGS)):
            sugg = set(e[f"suggested_{dim}"].split())
            fin = _flags(m, flist)
            for f in flist:
                flags[dim][f]["suggested"] += int(f in sugg)
                flags[dim][f]["final"] += int(f in fin)
                flags[dim][f]["both"] += int(f in sugg and f in fin)
    return {"n_compared": len(compared), "n_decided": len(decided), "totals": totals,
            "by_extractor": dict(sorted(by_ext.items())), "by_period": dict(sorted(by_period.items())),
            "type_confusion": {t: dict(c) for t, c in confusion.items()}, "flags": flags,
            "dimensions": list(DIMENSIONS)}


LABELS = {"type": "Type", "domains": "Domains", "issues": "Issues", "dyads": "Dyads", "grouping": "Grouping", "all_three": "Type, Domains and Issues all"}


def markdown(r: dict) -> str:
    def cell(c, d):
        return f"{c[d]['agree']}/{c[d]['n']}" if c[d]["n"] else "–"
    lines = [f"Compared events: {r['n_compared']} (decided suggestions: {r['n_decided']}).", "",
             "| Extractor | n | " + " | ".join(LABELS[d] for d in DIMENSIONS) + " | accepted | merged | rejected |",
             "|---|---|" + "---|" * (len(DIMENSIONS) + 3)]
    for name, c in list(r["by_extractor"].items()) + [("all", r["totals"])]:
        lines.append(f"| {name} | {c['n']} | " + " | ".join(cell(c, d) for d in DIMENSIONS) + f" | {c['outcome']['accepted']} | {c['outcome']['merged']} | {c['outcome']['rejected']} |")
    lines += ["", "| Period | n | " + " | ".join(LABELS[d] for d in DIMENSIONS) + " |", "|---|---|" + "---|" * len(DIMENSIONS)]
    for name, c in r["by_period"].items():
        lines.append(f"| {name} | {c['n']} | " + " | ".join(cell(c, d) for d in DIMENSIONS) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=ROOT / "data")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    with open(a.data / "events.csv", newline="", encoding="utf-8") as f:
        events = list(csv.DictReader(f))
    with open(a.data / "moves.csv", newline="", encoding="utf-8") as f:
        moves = list(csv.DictReader(f))
    r = report(events, moves)
    print(json.dumps(r, indent=1) if a.json else markdown(r), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
