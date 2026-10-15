"""The review queue: a harvest run becomes a pull request; the coder's decisions become commits.

  open    append a run's candidates to data/events.csv and data/sources.csv on a branch, write the
          review page, commit, and (unless --no-push) push and open the pull request
  page    (re)generate the review page for the candidates currently in data/events.csv
  decide  apply a decisions file to the canonical files: reject, merge into an existing move, or
          form a new move (optionally with field edits); then commit on the current branch

The review page is a self-contained HTML file: the coder opens it from the checked-out branch, makes
decisions in the browser, exports decisions.json, and runs `decide`. Only decisions applied through
`decide` change the files (ADR 0003, 0004); the page itself writes nothing.

Usage:
  python -m pipeline.queue open   --run harvest/runs/<run_id> [--no-push]
  python -m pipeline.queue page   [--out docs/review/<run_id>.html]
  python -m pipeline.queue decide decisions.json --reviewer "Name" [--date YYYY-MM-DD] [--no-commit]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipeline import schema

TEMPLATES = Path(__file__).resolve().parent / "templates"
REPO = "South-China-Sea-Developments/SCS-Developments-Tracker"


def repo_root(start: Path | None = None) -> Path:
    """The checkout the command runs in (its git top level), not where the package is installed."""
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start or Path.cwd(), capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("not inside a git checkout; run from the repository")
    return Path(r.stdout.strip())


# ---------------------------------------------------------------------------
# files

def read_table(name: str, data_dir: Path) -> list[dict]:
    with open(data_dir / f"{name}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_table(name: str, rows: list[dict], data_dir: Path) -> None:
    cols = schema.TABLES[name]
    with open(data_dir / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def git(*args: str, cwd: Path, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip()


# ---------------------------------------------------------------------------
# open: run -> branch + files + page + PR

def append_run(run_dir: Path, data_dir: Path) -> tuple[int, int]:
    """Append a run's candidates and sources to the canonical files; skip ids already present."""
    cand = []
    with open(run_dir / "candidates.csv", newline="", encoding="utf-8") as f:
        cand = list(csv.DictReader(f))
    with open(run_dir / "sources.csv", newline="", encoding="utf-8") as f:
        srcs = list(csv.DictReader(f))
    events = read_table("events", data_dir)
    sources = read_table("sources", data_dir)
    have_e = {e["event_id"] for e in events}
    have_s = {s["source_id"] for s in sources}
    new_e = [c for c in cand if c["event_id"] not in have_e]
    new_s = [s for s in srcs if s["source_id"] not in have_s and s["event_id"] in have_e | {c["event_id"] for c in new_e}]
    write_table("events", events + new_e, data_dir)
    write_table("sources", sources + new_s, data_dir)
    return len(new_e), len(new_s)


def cmd_open(args) -> int:
    root = repo_root()
    data_dir = root / "data"
    run_dir = Path(args.run).resolve()
    run_id = run_dir.name
    report = json.loads((run_dir / "run.json").read_text(encoding="utf-8")) if (run_dir / "run.json").exists() else {}
    branch = f"harvest/{run_id}"
    base = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    if git("status", "--porcelain", "--", "data", cwd=root):
        print("data/ has uncommitted changes; commit or stash them first", file=sys.stderr)
        return 1
    git("checkout", "-b", branch, cwd=root)
    n_e, n_s = append_run(run_dir, data_dir)
    page = root / "docs" / "review" / f"{run_id}.html"
    write_review_page(page, data_dir, run_id=run_id)
    git("add", "data/events.csv", "data/sources.csv", str(page.relative_to(root)), cwd=root)
    if (root / "harvest" / "state.json").exists():
        git("add", "harvest/state.json", cwd=root)
    git("commit", "-q", "-m", f"Harvest {run_id}: {n_e} candidate events for review\n\nExtractor: {report.get('extractor', '?')}. "
        f"Documents: {report.get('documents', '?')}. Review page: docs/review/{run_id}.html", cwd=root)
    print(f"branch {branch}: {n_e} candidate events, {n_s} sources, review page {page.relative_to(root)}")
    if args.no_push:
        return 0
    git("push", "-q", "-u", "origin", branch, cwd=root)
    body = (f"Candidate events from harvest run `{run_id}` ({n_e} events, {n_s} sources). "
            f"Extractor: `{report.get('extractor', '?')}`; documents: {report.get('documents', '?')}; "
            f"possible duplicates flagged: {report.get('duplicates', '?')}.\n\n"
            f"**How to review:** check out this branch, open `docs/review/{run_id}.html` in a browser, decide each candidate, "
            f"export `decisions.json`, then run `python -m pipeline.queue decide decisions.json --reviewer \"Your name\"` and push. "
            f"Merging this pull request is acceptance; the validator must pass first.\n\n"
            f"Nothing here enters the dataset until it is reviewed (ADR 0003).")
    r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/pulls", "-f", f"title=Harvest {run_id}: {n_e} candidate events for review",
                        "-f", f"head={branch}", "-f", f"base={base}", "-f", f"body={body}", "--jq", ".html_url"],
                       cwd=root, capture_output=True, text=True)
    if r.returncode:
        print(f"pull request not opened: {r.stderr.strip()[:300]}", file=sys.stderr)
        return 1
    print(f"pull request: {r.stdout.strip()}")
    return 0


# ---------------------------------------------------------------------------
# the review page

def review_context(data_dir: Path, run_id: str | None = None) -> dict:
    events = read_table("events", data_dir)
    sources = read_table("sources", data_dir)
    moves = read_table("moves", data_dir)
    claimants = {c["code"]: c["name"] for c in read_table("claimants", data_dir)}
    by_event: dict[str, list[dict]] = {}
    for s in sources:
        by_event.setdefault(s["event_id"], []).append(s)
    cands = [e for e in events if e["status"] == "candidate" and (not run_id or e["harvest_run_id"] == run_id)]
    move_index = {m["move_id"]: m for m in moves}

    def brief(m: dict) -> dict:
        return {"move_id": m["move_id"], "year": m["year"], "types": [t for t in schema.TYPE_FLAGS if m[t] == "1"],
                "description": m["description"][:300], "status": m["status"], "coded_by": m["coded_by"]}

    items = []
    for e in cands:
        year = int(e["date_start"][:4]) if e["date_start"][:4].isdigit() else None
        prev = [brief(m) for m in moves if m["claimant"] == e["claimant"] and year and int(m["year"]) == year - 1]
        same = [brief(m) for m in moves if m["claimant"] == e["claimant"] and year and int(m["year"]) == year]
        dup = ""
        if e["review_note"].startswith("Possible duplicate of "):
            dup = e["review_note"].split("Possible duplicate of ", 1)[1].rstrip(".")
        dup_event = next((x for x in events if x["event_id"] == dup), None)
        items.append({"event": e, "sources": by_event.get(e["event_id"], []), "year": year, "previous_year_moves": prev,
                      "same_year_moves": same, "duplicate_of": dup_event, "claimant_name": claimants.get(e["claimant"], e["claimant"])})
    return {"run_id": run_id or "all", "items": items, "claimants": claimants,
            "types": [(t, schema.TYPE_LABELS[t]) for t in schema.TYPE_FLAGS],
            "domains": [(d, schema.DOMAIN_LABELS[d]) for d in schema.DOMAIN_FLAGS],
            "issues": [(i, schema.ISSUE_LABELS[i]) for i in schema.ISSUE_FLAGS],
            "subregions": list(zip(range(1, 11), schema.SUBREGION_NAMES)),
            "criteria": schema.INTENSIFICATION_CRITERIA, "generated": dt.date.today().isoformat(),
            "move_index": move_index}


def write_review_page(path: Path, data_dir: Path, run_id: str | None = None) -> int:
    ctx = review_context(data_dir, run_id)
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    ctx_json = json.dumps({"run_id": ctx["run_id"], "items": ctx["items"]}, ensure_ascii=False).replace("</", "<\\/")
    html = env.get_template("review.html").render(ctx_json=ctx_json, **ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return len(ctx["items"])


def cmd_page(args) -> int:
    root = repo_root()
    out = Path(args.out) if args.out else root / "docs" / "review" / f"{args.run_id or 'all'}.html"
    n = write_review_page(out, root / "data", run_id=args.run_id or None)
    print(f"{n} candidates -> {out}")
    return 0


# ---------------------------------------------------------------------------
# decide: decisions.json -> files

EDITABLE = ["date_start", "date_end", "date_precision", "lat", "lon", "location_name", "location_precision", "subregion",
            "summary", "actors"]


def next_move_id(claimant: str, year: int, moves: list[dict]) -> str:
    used = {int(m["move_id"][-2:]) for m in moves if m["move_id"].startswith(f"{claimant}{year}") and m["move_id"][-2:].isdigit()}
    n = 1
    while n in used:
        n += 1
    return f"{claimant}{year}{n:02d}"


def apply_decisions(decisions: list[dict], reviewer: str, date: str, data_dir: Path) -> dict:
    """Mutates the canonical files. Returns counts. Raises ValueError on an invalid decision (nothing written)."""
    events = read_table("events", data_dir)
    moves = read_table("moves", data_dir)
    by_id = {e["event_id"]: e for e in events}
    move_ids = {m["move_id"] for m in moves}
    counts = {"rejected": 0, "merged": 0, "new_moves": 0, "accepted_events": 0}
    new_moves: list[dict] = []

    for d in decisions:
        eid = d.get("event_id")
        e = by_id.get(eid)
        if not e:
            raise ValueError(f"decision for unknown event {eid!r}")
        if e["status"] != "candidate":
            raise ValueError(f"event {eid} is {e['status']}, not a candidate")
        action = d.get("action")
        note = (d.get("note") or "").strip()
        for k, v in (d.get("edits") or {}).items():
            if k not in EDITABLE:
                raise ValueError(f"{eid}: field {k!r} is not editable at review")
            e[k] = str(v)
        if action == "reject":
            if not note:
                raise ValueError(f"{eid}: a rejection needs a note")
            e["status"] = "rejected"
            counts["rejected"] += 1
        elif action == "merge":
            target = d.get("move_id", "")
            if target not in move_ids:
                raise ValueError(f"{eid}: merge target {target!r} does not exist")
            e["move_id"] = target
            e["status"] = "accepted"
            counts["merged"] += 1
            counts["accepted_events"] += 1
        elif action == "new_move":
            spec = d.get("new_move") or {}
            crit = spec.get("intensification_criterion", "")
            if crit not in schema.INTENSIFICATION_CRITERIA:
                raise ValueError(f"{eid}: a new move needs intensification_criterion in {schema.INTENSIFICATION_CRITERIA}")
            t = spec.get("type")
            if t not in schema.TYPE_FLAGS:
                raise ValueError(f"{eid}: a new move needs exactly one type")
            year = int(spec.get("year") or e["date_start"][:4])
            claimant = e["claimant"]
            mid = spec.get("move_id") or next_move_id(claimant, year, moves + new_moves)
            if mid in move_ids:
                raise ValueError(f"{eid}: move {mid} already exists")
            m = {c: "" for c in schema.TABLES["moves"]}
            for f in schema.FLAG_COLUMNS:
                m[f] = "0"
            m[t] = "1"
            for dmn in spec.get("domains", []):
                if dmn in schema.DOMAIN_FLAGS:
                    m[dmn] = "1"
            for iss in spec.get("issues", []):
                if iss in schema.ISSUE_FLAGS:
                    m[iss] = "1"
            for sub in spec.get("subregions", []):
                if str(sub) in {str(i) for i in range(1, 11)}:
                    m[schema.SUBREGION_FLAGS[int(sub) - 1]] = "1"
            dyads = [x for x in spec.get("dyads", []) if isinstance(x, str) and 1 <= len(x) <= 2 and set(x) <= schema.DYAD_LETTERS]
            m.update(move_id=mid, claimant=claimant, year=str(year), instance_no=str(int(mid[-2:])),
                     dyads=" ".join(dyads), description=(spec.get("description") or e["summary"]).strip(),
                     ongoing_through=str(spec.get("ongoing_through") or year), ongoing_through_notes="",
                     intensification_criterion=crit, coded_by="project", coder=reviewer, coding_date=date,
                     data_version=schema.DATASET_VERSION, status="accepted")
            new_moves.append(m)
            move_ids.add(mid)
            e["move_id"] = mid
            e["status"] = "accepted"
            counts["new_moves"] += 1
            counts["accepted_events"] += 1
        else:
            raise ValueError(f"{eid}: unknown action {action!r}")
        e["reviewer"] = reviewer
        e["review_date"] = date
        if note:
            e["review_note"] = (e["review_note"] + " " + note).strip() if e["review_note"] else note

    write_table("events", events, data_dir)
    if new_moves:
        write_table("moves", moves + new_moves, data_dir)
    return counts


def cmd_decide(args) -> int:
    decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    if isinstance(decisions, dict):
        decisions = decisions.get("decisions", [])
    date = args.date or dt.date.today().isoformat()
    root = repo_root()
    if not args.reviewer.strip():
        print("a reviewer name is required", file=sys.stderr)
        return 1
    counts = apply_decisions(decisions, args.reviewer.strip(), date, root / "data")
    print(f"applied {len(decisions)} decisions: {counts}")
    if args.no_commit:
        return 0
    git("add", "data/events.csv", "data/moves.csv", cwd=root)
    git("commit", "-q", "-m", f"Review by {args.reviewer}: {counts['rejected']} rejected, {counts['merged']} merged, "
        f"{counts['new_moves']} new moves\n\nDecisions applied with pipeline.queue decide on {date}.", cwd=root)
    print("committed; push and let the validator run")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    so = sub.add_parser("open"); so.add_argument("--run", required=True); so.add_argument("--no-push", action="store_true"); so.set_defaults(fn=cmd_open)
    sp = sub.add_parser("page"); sp.add_argument("--out", default=""); sp.add_argument("--run-id", default=""); sp.set_defaults(fn=cmd_page)
    sd = sub.add_parser("decide"); sd.add_argument("decisions"); sd.add_argument("--reviewer", required=True)
    sd.add_argument("--date", default=""); sd.add_argument("--no-commit", action="store_true"); sd.set_defaults(fn=cmd_decide)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
