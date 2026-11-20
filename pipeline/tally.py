"""Tallies of harvested candidates by claimant, year and practice: a pointer to where a frequency
source is worth looking for, never a count to cite (ticket 25).

A frequency move (coding guide, Part II) needs two comparable numbers for the same kind of act in
consecutive years, or a source that states the increase. The harvest is not that: it is what the
sources reported and the compilers found, and reporting density varies by a factor of ten across the
series. So this module only classifies each candidate into a practice by the words of its summary and
counts them, so that a coder deciding a 2016 China row can see at a glance that the candidates hold
five sinkings against 2015's one — and then go to `docs/notes/frequency-sources.md` for the series that
can carry the claim.

    python -m pipeline.tally                      # writes docs/reports/candidate-tallies.md
    python -m pipeline.tally --chubb-increases    # prints Chubb's moves worded as increases, with the sources cited
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The practices, in the order the tables show them; the first pattern that matches the summary wins,
# so the more specific practices come first. A candidate matching none is "other".
PRACTICES: list[tuple[str, str]] = [
    ("sinking/ramming", r"\b(sank|sunk|sink|sinking|ramm(ed|ing)|collid(ed|ing|sion))\b"),
    ("fisher enforcement", r"\b(fisher|fishing boat|fishing vessel|trawler)s?\b.*\b(expel|chase|drove|driven|harass|detain|arrest|seiz|confiscat|water cannon|board)|\b(expel|chased|detain|arrest|seiz|harass)\w*\b.*\b(fisher|fishing)"),
    ("detention/arrest", r"\b(detain|arrest|held|seized|captur)\w*\b.*\b(crew|vessel|boat|ship|national)s?\b"),
    ("interception (air/sea)", r"\b(intercept|shadow|challeng|warn(ed|ing)? off|unsafe|blocked|blocking|blockade|boarded|resupply|water cannon|laser)\w*\b|\b(aircraft|plane|warship|destroyer|navy ship)\b.*\b(intercept|shadow|challeng|expel)"),
    ("exercise/drill", r"\b(exercise|drill|live[- ]fire|war ?game)s?\b"),
    ("patrol/presence", r"\b(patrol|presence|deploy|station|anchor|loiter|swarm|flotilla|militia)\w*\b"),
    ("diplomatic statement", r"\b(protest|spokes|note verbale|summon|démarche|demarche|condemn|rejected|reiterat|urged|lodged|statement)\w*\b"),
    ("energy/survey", r"\b(oil|gas|drill(ing)? rig|rig\b|survey|seismic|exploration|block|cnooc|petro|hydrocarbon|pipeline)\w*\b"),
    ("legislation/administration", r"\b(laws?\b(?!-enforcement)|regulation|decree|ordinance|baseline|named|names|administrative|jurisdiction|\bban\b|moratorium|licen[cs]e|permit|map\b|passport|county|city established|census)"),
    ("occupation/landing", r"\b(occup|landed|landing|garrison|marker|flag|visit(ed|s)?\b|flew to|inspection tour)\w*\b"),
    ("construction/reclamation", r"\b(reclamation|reclaim|dredg|construct|build|runway|airstrip|hangar|radar|lighthouse|facilit|installation|outpost|harbou?r|wharf|pier)\w*\b"),
]
_COMPILED = [(name, re.compile(p, re.I)) for name, p in PRACTICES]


def practice(summary: str) -> str:
    """The practice a candidate's summary describes, by the first matching pattern, else "other"."""
    text = summary or ""
    for name, rx in _COMPILED:
        if rx.search(text):
            return name
    return "other"


def load_candidates(root: Path = ROOT) -> list[dict]:
    """Every candidate in the compiled sets (harvest/manual/*.json) and every harvested row of
    data/events.csv (the weekly runs; candidate, accepted, merged or rejected alike), one dict per event
    with claimant, year, summary and practice. The manual sets are the backfill's candidates whatever
    the review's state; a harvested event appears once even when it is in both."""
    out: dict[str, dict] = {}

    def key(e: dict) -> str:
        return f"{e['claimant']}|{e['date_start']}|{(e['summary'] or '')[:60]}"

    for f in sorted(glob.glob(str(root / "harvest" / "manual" / "*.json"))):
        for e in json.loads(Path(f).read_text(encoding="utf-8")):
            out[key(e)] = {"claimant": e["claimant"], "year": e["date_start"][:4], "summary": e["summary"], "source": Path(f).name}
    ev = root / "data" / "events.csv"
    if ev.exists():
        with open(ev, newline="", encoding="utf-8") as fh:
            for e in csv.DictReader(fh):
                if e["harvest_run_id"] and not e["harvest_run_id"].startswith("seed") and key(e) not in out:
                    out[key(e)] = {"claimant": e["claimant"], "year": e["date_start"][:4], "summary": e["summary"], "source": e["harvest_run_id"]}
    rows = list(out.values())
    for r in rows:
        r["practice"] = practice(r["summary"])
    return rows


def tallies(rows: list[dict]) -> dict[str, dict[str, Counter]]:
    """{claimant: {year: Counter(practice)}}."""
    t: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        if r["year"].isdigit():
            t[r["claimant"]][r["year"]][r["practice"]] += 1
    return t


def report(rows: list[dict], today: str = "") -> str:
    """The markdown report: one table per claimant, years down, practices across, with the warning
    that these are counts of what was harvested."""
    names = [n for n, _ in PRACTICES] + ["other"]
    short = {"sinking/ramming": "sink/ram", "fisher enforcement": "fishers", "detention/arrest": "detain",
             "interception (air/sea)": "intercept", "exercise/drill": "exercise", "construction/reclamation": "build",
             "energy/survey": "energy", "patrol/presence": "patrol", "occupation/landing": "occupy",
             "legislation/administration": "law/admin", "diplomatic statement": "statement", "other": "other"}
    t = tallies(rows)
    lines = [
        "# Candidate tallies by claimant, year and practice",
        "",
        f"Generated by `python -m pipeline.tally` on {today or dt.date.today().isoformat()} from the compiled candidate sets",
        f"(`harvest/manual/*.json`) and the harvested rows of `data/events.csv`: {len(rows)} candidates.",
        "",
        "**These are counts of what the sources reported and the compilers found, not of what happened.** Reporting",
        "density differs by an order of magnitude across the series, so a column that doubles from one year to the",
        "next is a place to *look* for a frequency source (`docs/notes/frequency-sources.md`), never a number to cite.",
        "A frequency move needs two comparable figures for the same kind of act in consecutive years, or a source",
        "that states the increase (coding guide, Part II). The practice is read off the summary by keyword, so a",
        "candidate can sit in the wrong column; read the rows before trusting a cell.",
        "",
    ]
    for cl in sorted(t):
        lines += [f"## {cl}", "", "| year | " + " | ".join(short[n] for n in names) + " | all |",
                  "|---|" + "---|" * (len(names) + 1)]
        for y in sorted(t[cl]):
            c = t[cl][y]
            lines.append(f"| {y} | " + " | ".join(str(c[n]) if c[n] else "·" for n in names) + f" | {sum(c.values())} |")
        lines.append("")
    return "\n".join(lines)


_CITE = re.compile(r"\(([^()]*?(?:“|\"|,)[^()]*?)\)")
_INCREASE = re.compile(r"\b(increas\w*|more frequent|intensif\w*|stepped up|doubl\w*|from \d[\d,+]* .{0,40}? to \d[\d,+]*|at least \d+|expan\w*|accelerat\w*|ninefold|surge\w*)", re.I)


def chubb_increases(moves: list[dict]) -> list[dict]:
    """Chubb's moves whose description is worded as an increase — his frequency moves, and the sources
    he cited for the increase, parsed from the parentheses in the description."""
    out = []
    for m in moves:
        if m.get("coded_by") != "chubb":
            continue
        d = m["description"]
        hit = _INCREASE.search(d)
        if not hit:
            continue
        cites = [c.strip() for c in _CITE.findall(d)]
        out.append({"move_id": m["move_id"], "claimant": m["claimant"], "year": m["year"], "practice": practice(d),
                    "wording": hit.group(0), "sources": cites, "description": d})
    return out


def increases_markdown(items: list[dict]) -> str:
    """The generated section of docs/notes/frequency-sources.md: per claimant and practice, each of
    Chubb's increase-worded moves with its cited sources."""
    by: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for it in items:
        by[(it["claimant"], it["practice"])].append(it)
    lines = []
    for (cl, pr) in sorted(by):
        lines.append(f"### {cl} — {pr}")
        lines.append("")
        for it in sorted(by[(cl, pr)], key=lambda x: x["move_id"]):
            src = "; ".join(it["sources"]) if it["sources"] else "no source in parentheses"
            lines.append(f"- `{it['move_id']}` ({it['year']}, \"{it['wording']}\"): {src}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--out", type=Path, default=None, help="default docs/reports/candidate-tallies.md")
    p.add_argument("--date", default="")
    p.add_argument("--chubb-increases", action="store_true", help="print the generated section of docs/notes/frequency-sources.md instead")
    a = p.parse_args(argv)
    if a.chubb_increases:
        with open(a.root / "data" / "moves.csv", newline="", encoding="utf-8") as fh:
            md = increases_markdown(chubb_increases(list(csv.DictReader(fh))))
        note = a.root / "docs" / "notes" / "frequency-sources.md"
        if note.exists() and "<!-- generated: start -->" in note.read_text(encoding="utf-8"):
            s = note.read_text(encoding="utf-8")
            head, rest = s.split("<!-- generated: start -->", 1)
            tail = rest.split("<!-- generated: end -->", 1)[1]
            note.write_text(f"{head}<!-- generated: start -->\n{md}\n<!-- generated: end -->{tail}", encoding="utf-8")
            print(f"generated section refreshed in {note}")
        else:
            print(md)
        return 0
    rows = load_candidates(a.root)
    out = a.out or a.root / "docs" / "reports" / "candidate-tallies.md"
    out.write_text(report(rows, a.date) + "\n", encoding="utf-8")
    print(f"{len(rows)} candidates tallied -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
