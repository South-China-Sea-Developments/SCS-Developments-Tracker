"""The review queue: a harvest run becomes a pull request; the coder's decisions become commits.

  open    append a run's candidates to data/events.csv and data/sources.csv on a branch, write the
          review page, commit, and (unless --no-push) push and open the pull request
  page    (re)generate the review page for the candidates currently in data/events.csv
  decide  apply a decisions file to the canonical files, all or nothing: reject, merge into an
          existing move (or one formed in the same batch), form a new move, or mark a duplicate of
          an accepted event; edits ride on any of them; the validator runs before anything is
          written; then commit on the current branch

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
import os
import subprocess
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipeline import gazetteer, schema

TEMPLATES = Path(__file__).resolve().parent / "templates"
REPO = os.environ.get("GITHUB_REPOSITORY") or "South-China-Sea-Developments/SCS-Developments-Tracker"


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
    new_e = [gazetteer.locate(c) for c in cand if c["event_id"] not in have_e]   # named features get coordinates
    new_s = [s for s in srcs if s["source_id"] not in have_s and s["event_id"] in have_e | {c["event_id"] for c in new_e}]
    write_table("events", events + new_e, data_dir)
    write_table("sources", sources + new_s, data_dir)
    return len(new_e), len(new_s)


def cmd_open(args) -> int:
    root = repo_root()
    data_dir = root / "data"
    run_dir = Path(args.run).resolve()
    run_id = run_dir.name
    for name in ("candidates.csv", "sources.csv"):
        if not (run_dir / name).exists():
            print(f"{run_dir / name} is missing; is {run_dir} a harvest run folder?", file=sys.stderr)
            return 1
    report = json.loads((run_dir / "run.json").read_text(encoding="utf-8")) if (run_dir / "run.json").exists() else {}
    with open(run_dir / "candidates.csv", newline="", encoding="utf-8") as f:
        n_cand = sum(1 for _ in csv.DictReader(f))
    if not n_cand:
        print(f"run {run_id} has no candidates; nothing to review, no branch made")
        return 0
    branch = f"harvest/{run_id}"
    if git("status", "--porcelain", "--", "data", cwd=root):
        print("data/ has uncommitted changes; commit or stash them first", file=sys.stderr)
        return 1
    exists = git("branch", "--list", branch, cwd=root)
    git("checkout", "-q", branch if exists else "-b", *([] if exists else [branch]), cwd=root)
    if exists:
        print(f"resuming existing branch {branch}")
    n_e, n_s = append_run(run_dir, data_dir)
    page = root / "docs" / "review" / f"{run_id}.html"
    write_review_page(page, data_dir, run_id=run_id)
    git("add", "data/events.csv", "data/sources.csv", str(page.relative_to(root)), cwd=root)
    if git("status", "--porcelain", "--", "data", str(page.relative_to(root)), cwd=root):
        git("commit", "-q", "-m", f"Harvest {run_id}: {n_e} candidate events for review\n\nExtractor: {report.get('extractor', '?')}. "
            f"Documents: {report.get('documents', '?')}. Review page: docs/review/{run_id}.html", cwd=root)
    print(f"branch {branch}: {n_e} new candidate events, {n_s} sources, review page {page.relative_to(root)}")
    if args.no_push:
        return 0
    try:
        git("push", "-q", "-u", "origin", branch, cwd=root)
    except RuntimeError as e:
        print(f"push failed ({e}); fix the remote and run the same command again to resume", file=sys.stderr)
        return 1
    existing = subprocess.run(["gh", "api", f"repos/{REPO}/pulls?head={REPO.split('/')[0]}:{branch}&state=open", "--jq", ".[0].html_url"],
                              cwd=root, capture_output=True, text=True)
    if existing.returncode == 0 and existing.stdout.strip():
        print(f"pull request already open: {existing.stdout.strip()}")
        return 0
    body = (f"Candidate events from harvest run `{run_id}` ({n_cand} events). "
            f"Extractor: `{report.get('extractor', '?')}`; documents: {report.get('documents', '?')}; "
            f"possible duplicates flagged: {report.get('duplicates', '?')}.\n\n"
            f"**How to review:** `git checkout {branch}`, open `docs/review/{run_id}.html` in a browser, decide each candidate, "
            f"export the decisions file, then run `python -m pipeline.queue decide decisions-{run_id}.json --reviewer \"Your name\"` and `git push`. "
            f"Merging this pull request is acceptance; the validator must pass first.\n\n"
            f"Nothing here enters the dataset until it is reviewed (ADR 0003).")
    r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/pulls", "-f", f"title=Harvest {run_id}: {n_cand} candidate events for review",
                        "-f", f"head={branch}", "-f", f"base={args.base}", "-f", f"body={body}", "--jq", ".html_url"],
                       cwd=root, capture_output=True, text=True)
    if r.returncode:
        print(f"branch pushed but the pull request was not opened: {r.stderr.strip()[:300]}\n"
              f"open it by hand from {branch} onto {args.base}, or run the same command again", file=sys.stderr)
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
        feat = gazetteer.resolve(e["location_name"]) if e["location_name"] else None
        e = dict(e, placed_name=feat["name_en"] if feat and e["lat"] and f"{feat['lat']:.5f}" == e["lat"] else "",
                 placed_area=feat["name_en"] if feat and not e["lat"] and e["subregion"] else "",
                 ambiguous=", ".join(f"{a['name_en']} (sub-region {a['subregion']})" for a in gazetteer.ambiguous(e["location_name"])) if e["location_name"] and not feat else "")
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


def _iso(s: str) -> str:
    try:
        return dt.date.fromisoformat(s).isoformat() if len(s) == 10 else ""
    except ValueError:
        return ""


def _check_edits(eid: str, e: dict, edits: dict) -> dict:
    """Validated edits; an empty value means keep (the page says 'leave blank to keep')."""
    out = {}
    for k, v in edits.items():
        if k not in EDITABLE:
            raise ValueError(f"{eid}: field {k!r} is not editable at review")
        v = str(v).strip()
        if v == "":
            continue
        if k in ("date_start", "date_end") and not _iso(v):
            raise ValueError(f"{eid}: {k} {v!r} is not an ISO date")
        if k == "date_precision" and v not in schema.DATE_PRECISION:
            raise ValueError(f"{eid}: date_precision must be one of {schema.DATE_PRECISION}")
        if k == "location_precision" and v not in schema.LOCATION_PRECISION:
            raise ValueError(f"{eid}: location_precision must be one of {schema.LOCATION_PRECISION}")
        if k == "subregion" and v not in {str(i) for i in range(1, 11)}:
            raise ValueError(f"{eid}: subregion must be 1-10")
        if k in ("lat", "lon"):
            try:
                f = float(v)
            except ValueError:
                raise ValueError(f"{eid}: {k} {v!r} is not a number")
            if not (-90 <= f <= 90 if k == "lat" else -180 <= f <= 180):
                raise ValueError(f"{eid}: {k} {v!r} is out of range")
            v = f"{f:.4f}"
        out[k] = v
    if "location_name" in out and not {"lat", "lon"} & out.keys():
        # a corrected name is placed afresh; the old coordinates do not survive it; a name the
        # gazetteer does not know leaves the event unplaced but keeps a stated sub-region
        probe = {"location_name": out["location_name"], "lat": "", "lon": "", "subregion": out.get("subregion", ""),
                 "location_precision": out.get("location_precision", "")}
        gazetteer.locate(probe)
        out["lat"], out["lon"] = probe["lat"], probe["lon"]
        if probe["lat"]:
            if "subregion" not in out:
                out["subregion"] = probe["subregion"]
            out["location_precision"] = probe["location_precision"] or "feature"
        else:
            kept = out.get("subregion", e["subregion"])
            if "subregion" not in out and probe["subregion"]:
                out["subregion"] = kept = probe["subregion"]
            if out.get("location_precision", e["location_precision"]) in ("", "unknown", "point", "feature"):
                out["location_precision"] = "subregion" if kept else "unknown"
    merged = {**e, **out}
    if bool(merged["lat"]) != bool(merged["lon"]):
        raise ValueError(f"{eid}: latitude and longitude go together; give both or neither")
    if merged["lat"] and merged["lon"]:
        if "subregion" not in out and ({"lat", "lon"} & out.keys()):
            sr = gazetteer.subregion_of(float(merged["lat"]), float(merged["lon"]))
            out["subregion"] = str(sr) if sr else e["subregion"]
        if "location_precision" not in out and ({"lat", "lon"} & out.keys()) and e["location_precision"] in ("", "unknown", "subregion"):
            out["location_precision"] = "point"
    elif merged["location_precision"] == "point":
        raise ValueError(f"{eid}: location_precision 'point' needs coordinates")
    start, end = out.get("date_start", e["date_start"]), out.get("date_end", e["date_end"])
    if start and end and end < start:
        raise ValueError(f"{eid}: date_end is before date_start")
    return out


def next_move_id(claimant: str, year: int, moves: list[dict]) -> str:
    used = {int(m["move_id"][-2:]) for m in moves if m["move_id"].startswith(f"{claimant}{year}") and m["move_id"][-2:].isdigit()}
    n = 1
    while n in used:
        n += 1
    if n > 99:
        raise ValueError(f"{claimant} {year} already has 99 moves; the id scheme allows no more")
    return f"{claimant}{year}{n:02d}"


def _build_move(eid: str, e: dict, spec: dict, reviewer: str, date: str, moves: list[dict], existing_ids: set[str]) -> dict:
    crit = spec.get("intensification_criterion", "")
    if crit not in schema.INTENSIFICATION_CRITERIA:
        raise ValueError(f"{eid}: a new move needs intensification_criterion in {schema.INTENSIFICATION_CRITERIA}")
    t = spec.get("type")
    if t not in schema.TYPE_FLAGS:
        raise ValueError(f"{eid}: a new move needs exactly one type")
    year_s = str(spec.get("year") or e["date_start"][:4]).strip()
    if not year_s.isdigit():
        raise ValueError(f"{eid}: year {year_s!r} is not a year")
    year = int(year_s)
    claimant = e["claimant"]
    mid = str(spec.get("move_id") or "").strip() or next_move_id(claimant, year, moves)
    if not (mid.startswith(f"{claimant}{year}") and len(mid) == 8 and mid[-2:].isdigit()):
        raise ValueError(f"{eid}: move id {mid!r} must have the form {claimant}{year}NN")
    if mid in existing_ids:
        raise ValueError(f"{eid}: move {mid} already exists")
    for key, allowed in (("domains", schema.DOMAIN_FLAGS), ("issues", schema.ISSUE_FLAGS)):
        bad = [x for x in spec.get(key, []) if x not in allowed]
        if bad:
            raise ValueError(f"{eid}: unknown {key} {bad}")
    subs = [str(s) for s in spec.get("subregions", [])]
    if any(s not in {str(i) for i in range(1, 11)} for s in subs):
        raise ValueError(f"{eid}: sub-regions must be 1-10")
    dyads = [str(x).strip() for x in spec.get("dyads", []) if str(x).strip()]
    if any(not (1 <= len(x) <= 2 and set(x) <= schema.DYAD_LETTERS) for x in dyads):
        raise ValueError(f"{eid}: dyads must be one or two of the letters {''.join(sorted(schema.DYAD_LETTERS))}")
    ongoing = str(spec.get("ongoing_through") or year).strip()
    if not ongoing.isdigit() or int(ongoing) < year:
        raise ValueError(f"{eid}: ongoing_through must be a year not before {year}")
    m = {c: "" for c in schema.TABLES["moves"]}
    for f in schema.FLAG_COLUMNS:
        m[f] = "0"
    m[t] = "1"
    for x in spec.get("domains", []):
        m[x] = "1"
    for x in spec.get("issues", []):
        m[x] = "1"
    for s in subs:
        m[schema.SUBREGION_FLAGS[int(s) - 1]] = "1"
    m.update(move_id=mid, claimant=claimant, year=str(year), instance_no=str(int(mid[-2:])),
             dyads=" ".join(dyads), description=(spec.get("description") or e["summary"]).strip(),
             ongoing_through=ongoing, ongoing_through_notes="", intensification_criterion=crit,
             coded_by="project", coder=reviewer, coding_date=date, data_version=schema.DATASET_VERSION, status="accepted")
    return m


def apply_decisions(decisions: list[dict], reviewer: str, date: str, data_dir: Path,
                    xlsx_path: Path | None = None, mavd_path: Path | None = None) -> dict:
    """Apply a batch of decisions to the canonical files. All-or-nothing: an invalid decision, or a result
    the validator rejects, raises ValueError and writes nothing.

    Actions: reject (note required); merge (into an existing move, or into the move formed from another
    candidate in this batch via move_of_event); new_move; duplicate (of an accepted event: status merged).
    """
    events = read_table("events", data_dir)
    moves = read_table("moves", data_dir)
    by_id = {e["event_id"]: e for e in events}
    move_by_id = {m["move_id"]: m for m in moves}
    counts = {"rejected": 0, "merged": 0, "new_moves": 0, "duplicates": 0, "accepted_events": 0}
    new_moves: list[dict] = []
    move_of_event: dict[str, str] = {}

    for d in decisions:
        eid = d.get("event_id")
        if eid not in by_id:
            raise ValueError(f"decision for unknown event {eid!r}")
        if by_id[eid]["status"] != "candidate":
            raise ValueError(f"event {eid} is {by_id[eid]['status']}, not a candidate")
    if len({d["event_id"] for d in decisions}) != len(decisions):
        raise ValueError("an event has more than one decision in this batch")

    def finish(e: dict, d: dict, note: str):
        e["reviewer"] = reviewer
        e["review_date"] = date
        if note:
            e["review_note"] = (e["review_note"] + " | Reviewer: " + note) if e["review_note"] else note

    # pass 1: new moves (so merges can target them), rejections, duplicates
    pending_merges = []
    for d in decisions:
        eid, e = d["event_id"], by_id[d["event_id"]]
        action, note = d.get("action"), (d.get("note") or "").strip()
        edits = _check_edits(eid, e, d.get("edits") or {})
        if action == "reject":
            if not note:
                raise ValueError(f"{eid}: a rejection needs a note")
            e.update(edits); e["status"] = "rejected"; counts["rejected"] += 1; finish(e, d, note)
        elif action == "new_move":
            m = _build_move(eid, e, d.get("new_move") or {}, reviewer, date, moves + new_moves, set(move_by_id) | {x["move_id"] for x in new_moves})
            new_moves.append(m); move_of_event[eid] = m["move_id"]
            e.update(edits); e["move_id"] = m["move_id"]; e["status"] = "accepted"
            counts["new_moves"] += 1; counts["accepted_events"] += 1; finish(e, d, note)
        elif action == "duplicate":
            target = by_id.get(d.get("duplicate_of", ""))
            if not target or target["status"] != "accepted" or not target["move_id"]:
                raise ValueError(f"{eid}: duplicate_of must name an accepted event with a move")
            if target["claimant"] != e["claimant"]:
                raise ValueError(f"{eid}: duplicate_of names a {target['claimant']} event")
            e.update(edits); e["move_id"] = target["move_id"]; e["status"] = "merged"
            counts["duplicates"] += 1
            finish(e, d, f"Duplicate of {target['event_id']}." + (" " + note if note else ""))
        elif action == "merge":
            pending_merges.append((d, e, edits, note))
        else:
            raise ValueError(f"{eid}: unknown action {action!r}")

    # pass 2: merges, into existing moves or moves formed above
    all_moves = {**move_by_id, **{m["move_id"]: m for m in new_moves}}
    for d, e, edits, note in pending_merges:
        eid = e["event_id"]
        target = str(d.get("move_id") or "").strip()
        if d.get("move_of_event"):
            target = move_of_event.get(d["move_of_event"], "")
            if not target:
                raise ValueError(f"{eid}: {d['move_of_event']} does not form a new move in this batch")
        if target not in all_moves:
            raise ValueError(f"{eid}: merge target {target!r} does not exist")
        mv = all_moves[target]
        if mv["claimant"] != e["claimant"]:
            raise ValueError(f"{eid}: cannot merge a {e['claimant']} event into {target} ({mv['claimant']})")
        start = edits.get("date_start", e["date_start"])
        if start[:4] != mv["year"]:
            raise ValueError(f"{eid}: event is dated {start} but move {target} is {mv['year']}")
        e.update(edits); e["move_id"] = target; e["status"] = "accepted"
        counts["merged"] += 1; counts["accepted_events"] += 1; finish(e, d, note)

    # the merge gate, before anything is written
    import tempfile
    from pipeline.validate import validate
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        for name in ("claimants", "sources", "corrections"):
            (td / f"{name}.csv").write_bytes((data_dir / f"{name}.csv").read_bytes())
        write_table("events", events, td)
        write_table("moves", moves + new_moves, td)
        xlsx = xlsx_path or data_dir / "raw/mats-1.02/MATS_1-02_all_cases.xlsx"
        mavd = mavd_path or data_dir / "raw/mavd-arcgis-2023/All_Actions7.csv"
        errors = validate(td, xlsx if xlsx.exists() else None, mavd if mavd.exists() else None)
    if errors:
        raise ValueError("the result would not pass the validator:\n  " + "\n  ".join(errors[:10]))

    write_table("events", events, data_dir)
    if new_moves:
        write_table("moves", moves + new_moves, data_dir)
    return counts


def cmd_decide(args) -> int:
    payload = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    decisions = payload.get("decisions", []) if isinstance(payload, dict) else payload
    if not decisions:
        print("the decisions file holds no decisions", file=sys.stderr)
        return 1
    date = args.date or dt.date.today().isoformat()
    root = repo_root()
    reviewer = (args.reviewer or (payload.get("reviewer", "") if isinstance(payload, dict) else "")).strip()
    if not reviewer:
        print("a reviewer name is required (--reviewer, or the reviewer field of the decisions file)", file=sys.stderr)
        return 1
    try:
        counts = apply_decisions(decisions, reviewer, date, root / "data")
    except ValueError as e:
        print(f"nothing applied: {e}", file=sys.stderr)
        return 1
    ids = ", ".join(sorted(d["event_id"] for d in decisions))
    print(f"applied {len(decisions)} decisions: {counts}")
    if args.no_commit:
        return 0
    git("add", "data/events.csv", "data/moves.csv", cwd=root)
    git("commit", "-q", "-m", f"Review by {reviewer}: {counts['rejected']} rejected, {counts['merged']} merged, "
        f"{counts['new_moves']} new moves, {counts['duplicates']} duplicates\n\nEvents: {ids}\nApplied with pipeline.queue decide on {date}.", cwd=root)
    print("committed; push and let the validator run")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    so = sub.add_parser("open"); so.add_argument("--run", required=True); so.add_argument("--no-push", action="store_true")
    so.add_argument("--base", default="main"); so.set_defaults(fn=cmd_open)
    sp = sub.add_parser("page"); sp.add_argument("--out", default=""); sp.add_argument("--run-id", default=""); sp.set_defaults(fn=cmd_page)
    sd = sub.add_parser("decide"); sd.add_argument("decisions"); sd.add_argument("--reviewer", default="")
    sd.add_argument("--date", default=""); sd.add_argument("--no-commit", action="store_true"); sd.set_defaults(fn=cmd_decide)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
