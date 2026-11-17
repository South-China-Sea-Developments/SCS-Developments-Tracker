"""The pre-sort (ticket 23): for every candidate of a review run, a suggestion of what the coder's decision
is likely to be, with a reason — so the coder confirms or overrides rather than constructs. Machines
propose, humans decide (ADR 0003): the pre-sort is a suggestion layer like `suggested_type`; nothing in it
changes a file until `pipeline.queue decide` applies the coder's own decisions.

A pre-sort lives in `harvest/presort/<run_id>.json`:

  {"run_id": ..., "presorted_by": "<who: a model name or a person>", "date": "YYYY-MM-DD",
   "items": [{"event_id": ..., "disposition": <one of DISPOSITIONS>, "of": <move_id or event_id>,
              "criterion": <novelty|frequency|scope, for new_move>, "group": <label, optional>,
              "reason": "<one or two sentences>"}, ...]}

Dispositions:
  continuation  the act continues a move of the previous year (or an earlier move still ongoing) at the
                same level: `of` names that move; the likely decision is reject with the note
                "continuation of <move_id>" and an extension of that move's ongoing_through
  same_move     the act belongs with another candidate of the same run and claimant-year that would form
                the move: `of` names that candidate (the one proposed as the move's lead)
  new_move      the act is an intensification against the previous year: `criterion` says which kind
  duplicate     another report of the same incident: `of` names the event (a candidate of the run, or
                an accepted event)
  unclear       the pre-sorter could not tell; the coder starts from nothing

Usage:
  python -m pipeline.presort context --run <run_id> --out ctx.json [--data DIR]   what a pre-sorter needs: the
        run's candidates (titles, not excerpts), the claimant's accepted moves of the previous and same year
        for every claimant-year in the run, and the baseline file for a 1970 year
  python -m pipeline.presort check --run <run_id> --file harvest/presort/<run_id>.json [--data DIR]   validate
        the file against the run: every candidate covered once, dispositions known, `of` resolvable,
        criterion present on new_move
`pipeline.queue page --run-id <run_id>` reads the file when it exists and renders it; the Airtable records
carry it as the `presort` field.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline import schema
from pipeline.queue import read_table, repo_root

DISPOSITIONS = ["continuation", "same_move", "new_move", "duplicate", "unclear"]
NEEDS_OF = {"continuation", "same_move", "duplicate"}


def default_path(run_id: str, root: Path | None = None) -> Path:
    return (root or repo_root()) / "harvest" / "presort" / f"{run_id}.json"


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _candidates(data_dir: Path, run_id: str) -> list[dict]:
    return [e for e in read_table("events", data_dir) if e["status"] == "candidate" and e["harvest_run_id"] == run_id]


def _brief(m: dict) -> dict:
    return {"move_id": m["move_id"], "year": m["year"], "types": [t for t in schema.TYPE_FLAGS if m[t] == "1"],
            "dyads": m["dyads"], "ongoing_through": m["ongoing_through"], "coded_by": m["coded_by"],
            "description": m["description"]}


def context(data_dir: Path, run_id: str, root: Path | None = None) -> dict:
    """Everything a pre-sorter needs, in one JSON object: the candidates with their source titles, and for
    each claimant-year in the run the claimant's accepted moves of the previous year, of the same year, and
    of earlier years still ongoing into the previous year; the baseline file when a year is 1970."""
    root = root or repo_root()
    cands = _candidates(data_dir, run_id)
    sources = read_table("sources", data_dir)
    by_event: dict[str, list[dict]] = {}
    for s in sources:
        by_event.setdefault(s["event_id"], []).append({"title": s["title"], "publisher": s["publisher"], "pub_date": s["pub_date"], "url": s["url"]})
    moves = [m for m in read_table("moves", data_dir) if m["status"] == "accepted"]
    out_c = []
    for e in cands:
        out_c.append({k: e[k] for k in ("event_id", "claimant", "date_start", "date_end", "date_precision", "location_name",
                                        "subregion", "summary", "actors", "suggested_type", "suggested_domains",
                                        "suggested_issues", "suggested_dyads", "suggestion_reasoning", "review_note")}
                     | {"sources": by_event.get(e["event_id"], [])})
    ctx_moves: dict[str, list[dict]] = {}
    baselines: dict[str, str] = {}
    for cl, y in sorted({(c["claimant"], c["date_start"][:4]) for c in cands if c["date_start"][:4].isdigit()}):
        yi = int(y)
        prev = [m for m in moves if m["claimant"] == cl and m["year"].isdigit() and int(m["year"]) == yi - 1]
        same = [m for m in moves if m["claimant"] == cl and m["year"].isdigit() and int(m["year"]) == yi]
        ongoing = [m for m in moves if m["claimant"] == cl and m["year"].isdigit() and int(m["year"]) < yi - 1
                   and m["ongoing_through"].isdigit() and int(m["ongoing_through"]) >= yi - 1]
        ctx_moves[f"{cl}:{yi - 1}"] = [_brief(m) for m in prev]
        ctx_moves[f"{cl}:{yi}"] = [_brief(m) for m in same]
        ctx_moves[f"{cl}:ongoing-into-{yi - 1}"] = [_brief(m) for m in ongoing]
        if yi == 1970:
            b = root / "data" / "baselines" / f"{cl}.md"
            if b.exists():
                baselines[cl] = b.read_text(encoding="utf-8")
    return {"run_id": run_id, "candidates": out_c, "moves": ctx_moves, "baselines": baselines,
            "dispositions": DISPOSITIONS, "criteria": schema.INTENSIFICATION_CRITERIA}


def check(doc: dict, data_dir: Path, run_id: str) -> list[str]:
    """Errors that make a pre-sort unusable for the run; [] when it fits."""
    errs: list[str] = []
    if doc.get("run_id") != run_id:
        errs.append(f"run_id {doc.get('run_id')!r} is not {run_id!r}")
    if not doc.get("presorted_by"):
        errs.append("presorted_by is empty")
    cands = {e["event_id"]: e for e in _candidates(data_dir, run_id)}
    events = {e["event_id"]: e for e in read_table("events", data_dir)}
    moves = {m["move_id"]: m for m in read_table("moves", data_dir)}
    seen: set[str] = set()
    for i, it in enumerate(doc.get("items", [])):
        eid = it.get("event_id", "")
        where = f"item {i} ({eid or '?'})"
        if eid not in cands:
            errs.append(f"{where}: not a candidate of run {run_id}")
            continue
        if eid in seen:
            errs.append(f"{where}: listed twice")
        seen.add(eid)
        d = it.get("disposition")
        if d not in DISPOSITIONS:
            errs.append(f"{where}: unknown disposition {d!r}")
            continue
        if not (it.get("reason") or "").strip():
            errs.append(f"{where}: no reason")
        of = (it.get("of") or "").strip()
        if d in NEEDS_OF and not of:
            errs.append(f"{where}: {d} needs 'of'")
        if d == "continuation" and of and of not in moves:
            errs.append(f"{where}: continuation of unknown move {of}")
        if d == "continuation" and of in moves and moves[of]["claimant"] != cands[eid]["claimant"]:
            errs.append(f"{where}: {of} is a {moves[of]['claimant']} move")
        if d == "same_move" and of and (of not in cands or of == eid):
            errs.append(f"{where}: same_move must name another candidate of the run, not {of}")
        if d == "duplicate" and of and of not in events:
            errs.append(f"{where}: duplicate of unknown event {of}")
        if d == "new_move" and it.get("criterion") not in schema.INTENSIFICATION_CRITERIA:
            errs.append(f"{where}: new_move needs a criterion in {schema.INTENSIFICATION_CRITERIA}")
    for eid in sorted(set(cands) - seen):
        errs.append(f"{eid}: missing from the pre-sort")
    return errs


def label(it: dict) -> str:
    """The short form shown on the review page and in Airtable: 'continuation of CN201505'."""
    d = it.get("disposition", "")
    of = it.get("of", "")
    if d == "continuation":
        return f"continuation of {of}"
    if d == "same_move":
        return f"same move as {of}"
    if d == "new_move":
        return f"new move ({it.get('criterion', '')})"
    if d == "duplicate":
        return f"duplicate of {of}"
    return "unclear"


def by_event(doc: dict | None) -> dict[str, dict]:
    """{event_id: item} with the label added, for the page and the records."""
    if not doc:
        return {}
    return {it["event_id"]: dict(it, label=label(it), presorted_by=doc.get("presorted_by", "")) for it in doc.get("items", [])}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("context"); c.add_argument("--run", required=True); c.add_argument("--out", type=Path, required=True)
    c.add_argument("--data", type=Path, default=None)
    k = sub.add_parser("check"); k.add_argument("--run", required=True); k.add_argument("--file", type=Path, default=None)
    k.add_argument("--data", type=Path, default=None)
    a = p.parse_args(argv)
    data_dir = a.data or repo_root() / "data"
    if a.cmd == "context":
        ctx = context(data_dir, a.run)
        a.out.write_text(json.dumps(ctx, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{len(ctx['candidates'])} candidate(s) of {a.run} -> {a.out}")
        return 0
    path = a.file or default_path(a.run)
    errs = check(load(path), data_dir, a.run)
    if errs:
        print(f"{path}: {len(errs)} problem(s)", file=sys.stderr)
        for e in errs[:40]:
            print("  " + e, file=sys.stderr)
        return 1
    n = len(load(path)["items"])
    print(f"{path}: {n} item(s), fits run {a.run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
