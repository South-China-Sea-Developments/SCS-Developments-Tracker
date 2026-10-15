"""Operations for the scheduled run: harvest state across runs, failure issues, review reminders.

  state pull     fetch harvest/state.json (and the run log) from the `harvest-state` branch, if it exists
  state push     commit harvest/state.json and one run-log line back to that branch and push it
  failure-issue  open a GitHub issue for a failed run, or comment on the one already open
                 (--resolved: comment on and close the open one after a run succeeds)
  remind         comment on review pull requests older than N days, at most once per N days

The state branch holds only `state.json` (the item ids every source has yielded so far) and
`runs.jsonl` (one line per completed run: id, date, documents, candidates, tokens, cost, extractor).
It is never merged; it exists so that a run starts where the previous one stopped even when the
previous run's pull request is still open, and so that a failed run leaves the state untouched.

GitHub calls go through `gh api` with whatever token the environment carries (GH_TOKEN in CI).
`--dry-run` prints every write instead of making it.

Usage:
  python -m pipeline.ops state pull
  python -m pipeline.ops state push --run-id <id> [--report harvest/runs/<id>/run.json] [--captures harvest/captures/<id>]
  python -m pipeline.ops failure-issue --run-id <id> --run-url <url> [--resolved] [--dry-run]
  python -m pipeline.ops remind --maintainer <login> [--days 7] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from pipeline.queue import REPO, git, repo_root

STATE_BRANCH = "harvest-state"
FAILURE_LABEL = "harvest-failure"
FAILURE_TITLE = "Scheduled harvest run failed"
REMINDER_MARK = "<!-- scs-review-reminder -->"
FAILURE_MARK = "<!-- scs-harvest-failure -->"

Gh = Callable[..., Any]  # gh(method, path, **fields) -> parsed JSON (or None)


# ---------------------------------------------------------------------------
# GitHub

def gh_api(method: str, path: str, **fields) -> Any:
    """One `gh api` call; string fields go as -f, other JSON values as --input."""
    cmd = ["gh", "api", "-X", method, path]
    body = {k: v for k, v in fields.items() if v is not None}
    if body and any(not isinstance(v, str) for v in body.values()):
        r = subprocess.run(cmd + ["--input", "-"], input=json.dumps(body), capture_output=True, text=True)
    else:
        for k, v in body.items():
            cmd += ["-f", f"{k}={v}"]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"gh api {method} {path}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout) if r.stdout.strip() else None


def _dry(gh: Gh, dry_run: bool) -> Gh:
    """Reads go through; writes are printed instead."""
    if not dry_run:
        return gh

    def wrapped(method: str, path: str, **fields):
        if method == "GET":
            return gh(method, path, **fields)
        print(f"dry run: would {method} {path} {json.dumps(fields)[:200]}")
        return None
    return wrapped


# ---------------------------------------------------------------------------
# failure issues

def failure_issue(gh: Gh, run_id: str, run_url: str, resolved: bool = False, detail: str = "", dry_run: bool = False,
                  status: str = "failed") -> str:
    """Returns what was done: 'created', 'commented', 'closed' or 'nothing'."""
    gh = _dry(gh, dry_run)
    open_issues = [i for i in (gh("GET", f"repos/{REPO}/issues?state=open&per_page=100") or [])
                   if "pull_request" not in i and (FAILURE_LABEL in {l.get("name") for l in i.get("labels", [])}
                                                   or i.get("title") == FAILURE_TITLE or FAILURE_MARK in (i.get("body") or ""))]
    if resolved:
        if not open_issues:
            return "nothing"
        for i in open_issues:
            gh("POST", f"repos/{REPO}/issues/{i['number']}/comments",
               body=f"{FAILURE_MARK}\nScheduled run `{run_id}` succeeded: {run_url}. Closing.")
            gh("PATCH", f"repos/{REPO}/issues/{i['number']}", state="closed")
        return "closed"
    text = f"{FAILURE_MARK}\nScheduled harvest run `{run_id}` {status}: {run_url}\n\n{detail}".rstrip() + "\n"
    if open_issues:
        gh("POST", f"repos/{REPO}/issues/{open_issues[0]['number']}/comments", body=text)
        return "commented"
    gh("POST", f"repos/{REPO}/issues", title=FAILURE_TITLE, labels=[FAILURE_LABEL],
       body=text + "\nThe log is at the link above. This issue stays open while runs keep failing; each further "
                   "failure is a comment here, not a new issue. It closes itself after the next successful run.\n")
    return "created"


# ---------------------------------------------------------------------------
# review reminders

def _age_days(iso: str, now: dt.datetime) -> float:
    return (now - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 86400


def remind(gh: Gh, maintainer: str, days: int = 7, now: dt.datetime | None = None, dry_run: bool = False) -> list[int]:
    """Comments on every open `harvest/*` pull request older than `days` that has had no reminder in
    the last `days`. Returns the PR numbers reminded."""
    gh = _dry(gh, dry_run)
    now = now or dt.datetime.now(dt.timezone.utc)
    prs = gh("GET", f"repos/{REPO}/pulls?state=open&per_page=100") or []
    reminded = []
    for pr in prs:
        if not pr["head"]["ref"].startswith("harvest/"):
            continue
        age = _age_days(pr["created_at"], now)
        if age < days:
            continue
        since = (now - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        comments = gh("GET", f"repos/{REPO}/issues/{pr['number']}/comments?since={since}&per_page=100") or []
        recent = [c for c in comments if REMINDER_MARK in (c.get("body") or "") and _age_days(c["created_at"], now) < days]
        if recent:
            continue
        gh("POST", f"repos/{REPO}/issues/{pr['number']}/comments",
           body=f"{REMINDER_MARK}\n@{maintainer} this review has been open for {int(age)} days. "
                f"Candidates wait here until decided; nothing enters the dataset meanwhile (ADR 0003). "
                f"Review page: `docs/review/{pr['head']['ref'].split('/', 1)[1]}.html` on this branch.")
        reminded.append(pr["number"])
    return reminded


# ---------------------------------------------------------------------------
# state branch

def remote_branch_exists(root: Path, branch: str) -> bool:
    """True/False from the remote; raises on anything else (auth, network), because "no branch" and
    "could not ask" must not both become "start from an empty state"."""
    r = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch], cwd=root, capture_output=True, text=True)
    if r.returncode == 0:
        return True
    if r.returncode == 2:
        return False
    raise RuntimeError(f"could not query origin for {branch}: {r.stderr.strip()[:300]}")


def _fetch_branch(root: Path, branch: str) -> None:
    git("fetch", "-q", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}", cwd=root)


def state_pull(root: Path, branch: str = STATE_BRANCH) -> bool:
    """Writes harvest/state.json from the state branch; False (and no file) if the branch does not exist."""
    if not remote_branch_exists(root, branch):
        print(f"no {branch} branch on origin yet; starting from an empty state")
        return False
    _fetch_branch(root, branch)
    dest = root / "harvest" / "state.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(git("show", f"origin/{branch}:state.json", cwd=root) + "\n", encoding="utf-8")
    print(f"state restored from {branch}: {len(json.loads(dest.read_text(encoding='utf-8')).get('seen', []))} seen items")
    return True


def run_log_line(run_id: str, report: dict | None, now: dt.datetime | None = None, fetch_report: dict | None = None) -> dict:
    r = report or {}
    f = fetch_report or {}
    return {"run_id": run_id, "date": (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%MZ"),
            "documents": r.get("documents"), "candidates": r.get("candidates"), "duplicates": r.get("duplicates"),
            "input_tokens": r.get("input_tokens"), "output_tokens": r.get("output_tokens"),
            "estimated_cost_usd": r.get("estimated_cost_usd"), "extractor": r.get("extractor"), "failures": len(r.get("failures", [])),
            "sources_with_errors": sorted(s["source"] for s in f.get("sources", []) if s.get("errors"))}


def drop_failed(state_path: Path, report: dict | None, captures_dir: Path | None) -> int:
    """Removes from the state the documents whose extraction failed in this run, so the next run
    fetches and tries them again (the fetcher marks a document seen as soon as it has its text).
    Returns how many were dropped."""
    failed_ids = {f.get("capture_id") for f in (report or {}).get("failures", [])} - {None}
    if not failed_ids or not captures_dir or not Path(captures_dir).exists():
        return 0
    guids = set()
    for p in Path(captures_dir).rglob("*.json"):
        if p.name == "fetch-report.json":
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("capture_id") in failed_ids:
            guids.add(rec.get("guid"))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    before = len(state.get("seen", []))
    state["seen"] = sorted(set(state.get("seen", [])) - guids)
    state_path.write_text(json.dumps(state, indent=0), encoding="utf-8")
    return before - len(state["seen"])


def state_push(root: Path, run_id: str, report: dict | None = None, branch: str = STATE_BRANCH, now: dt.datetime | None = None,
               captures_dir: Path | None = None, fetch_report: dict | None = None) -> None:
    """Commits harvest/state.json and a run-log line to the state branch (created orphan if absent) and pushes."""
    state = root / "harvest" / "state.json"
    if not state.exists():
        raise RuntimeError(f"{state} does not exist; nothing to push")
    dropped = drop_failed(state, report, captures_dir)
    if dropped:
        print(f"{dropped} document(s) whose extraction failed will be retried next run")
    exists = remote_branch_exists(root, branch)
    if exists:
        _fetch_branch(root, branch)
    wt = Path(tempfile.mkdtemp(prefix="scs-state-"))
    # the local branch exists only for the length of this call; a stale one is left by an earlier failed push
    subprocess.run(["git", "branch", "-q", "-D", branch], cwd=root, capture_output=True)
    try:
        if exists:
            git("worktree", "add", "-q", str(wt), f"origin/{branch}", cwd=root)
            git("checkout", "-q", "-B", branch, cwd=wt)
        else:
            git("worktree", "add", "-q", "--detach", str(wt), cwd=root)
            git("checkout", "-q", "--orphan", branch, cwd=wt)
            git("rm", "-rfq", "--cached", ".", cwd=wt)
            for p in wt.iterdir():
                if p.name != ".git":
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
            (wt / "README.md").write_text(f"Harvest state for the scheduled run (`pipeline.ops`). `state.json`: item ids already "
                                          f"fetched per source. `runs.jsonl`: one line per completed run. Never merged.\n", encoding="utf-8")
        shutil.copyfile(state, wt / "state.json")
        with open(wt / "runs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(run_log_line(run_id, report, now, fetch_report)) + "\n")
        git("add", "-A", cwd=wt)
        git("commit", "-q", "-m", f"Harvest {run_id}: state after run", cwd=wt)
        git("push", "-q", "origin", f"{branch}:{branch}", cwd=wt)
        print(f"state pushed to {branch} (run {run_id})")
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=root, capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
        subprocess.run(["git", "branch", "-q", "-D", branch], cwd=root, capture_output=True)


# ---------------------------------------------------------------------------
# CLI

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("state"); s.add_argument("action", choices=["pull", "push"]); s.add_argument("--run-id", default="")
    s.add_argument("--report", default=""); s.add_argument("--captures", default=""); s.add_argument("--branch", default=STATE_BRANCH)
    f = sub.add_parser("failure-issue"); f.add_argument("--run-id", required=True); f.add_argument("--run-url", required=True)
    f.add_argument("--resolved", action="store_true"); f.add_argument("--detail", default=""); f.add_argument("--dry-run", action="store_true")
    f.add_argument("--status", default="failed", help="how the run ended, e.g. failure or cancelled")
    r = sub.add_parser("remind"); r.add_argument("--maintainer", required=True); r.add_argument("--days", type=int, default=7)
    r.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    if a.cmd == "state":
        root = repo_root()
        if a.action == "pull":
            state_pull(root, a.branch)
        else:
            if not a.run_id:
                p.error("state push needs --run-id")
            report = json.loads(Path(a.report).read_text(encoding="utf-8")) if a.report and Path(a.report).exists() else None
            fetch_path = Path(a.captures) / "fetch-report.json" if a.captures else None
            fetch_report = json.loads(fetch_path.read_text(encoding="utf-8")) if fetch_path and fetch_path.exists() else None
            state_push(root, a.run_id, report, a.branch, captures_dir=Path(a.captures) if a.captures else None, fetch_report=fetch_report)
        return 0
    if a.cmd == "failure-issue":
        print(failure_issue(gh_api, a.run_id, a.run_url, resolved=a.resolved, detail=a.detail, dry_run=a.dry_run, status=a.status))
        return 0
    if a.cmd == "remind":
        n = remind(gh_api, a.maintainer, a.days, dry_run=a.dry_run)
        print(f"reminded on {len(n)} pull request(s): {n}" if n else "no review pull request needs a reminder")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
