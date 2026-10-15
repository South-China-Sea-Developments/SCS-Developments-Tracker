"""The scheduled run's operations: state across runs, failure issues without duplicates, reminders.
GitHub is a recorded fake; the state branch is exercised against a local bare remote."""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

import pytest

from pipeline import ops

NOW = dt.datetime(2026, 10, 15, 6, 0, tzinfo=dt.timezone.utc)


class FakeGh:
    """Answers GETs from a table and records every write."""

    def __init__(self, responses: dict[str, object] | None = None):
        self.responses = responses or {}
        self.writes: list[tuple[str, str, dict]] = []

    def __call__(self, method, path, **fields):
        if method == "GET":
            for prefix, value in self.responses.items():
                if path.startswith(prefix):
                    return value
            return []
        self.writes.append((method, path, fields))
        return {"number": 99, "html_url": "https://example/99"}


# ---------------------------------------------------------------------------
# failure issues

def test_failure_creates_one_issue_with_label():
    gh = FakeGh()
    assert ops.failure_issue(gh, "20261015T0600", "https://ci/run/1", detail="fetch failed") == "created"
    (m, path, f), = gh.writes
    assert (m, path) == ("POST", f"repos/{ops.REPO}/issues")
    assert f["labels"] == [ops.FAILURE_LABEL] and "20261015T0600" in f["body"] and "fetch failed" in f["body"]
    assert ops.FAILURE_MARK in f["body"]


LABELLED = {"number": 12, "title": "something else", "labels": [{"name": ops.FAILURE_LABEL}]}


def test_repeated_failure_comments_instead_of_a_second_issue():
    gh = FakeGh({f"repos/{ops.REPO}/issues?state=open": [{"number": 3, "title": "unrelated", "labels": []}, LABELLED]})
    assert ops.failure_issue(gh, "r2", "https://ci/run/2") == "commented"
    (m, path, f), = gh.writes
    assert (m, path) == ("POST", f"repos/{ops.REPO}/issues/12/comments") and "r2" in f["body"]


def test_pull_requests_in_the_issue_list_are_not_failure_issues():
    gh = FakeGh({f"repos/{ops.REPO}/issues?state=open": [dict(LABELLED, number=5, pull_request={})]})
    assert ops.failure_issue(gh, "r", "u") == "created"


@pytest.mark.parametrize("issue", [{"number": 7, "title": ops.FAILURE_TITLE, "labels": []},
                                   {"number": 8, "title": "x", "labels": [], "body": f"{ops.FAILURE_MARK}\nold"}])
def test_an_open_failure_issue_is_recognised_without_its_label(issue):
    """GitHub drops labels when the token may not set them; the title and the body marker still identify the issue."""
    gh = FakeGh({f"repos/{ops.REPO}/issues?state=open": [issue]})
    assert ops.failure_issue(gh, "r", "u") == "commented" and gh.writes[0][1].endswith(f"/issues/{issue['number']}/comments")


def test_cancelled_runs_are_reported_with_their_status():
    gh = FakeGh()
    ops.failure_issue(gh, "r", "u", status="cancelled")
    assert "`r` cancelled: u" in gh.writes[0][2]["body"]


def test_success_closes_the_open_failure_issue_and_is_quiet_otherwise():
    gh = FakeGh({f"repos/{ops.REPO}/issues?state=open": [LABELLED]})
    assert ops.failure_issue(gh, "r3", "https://ci/run/3", resolved=True) == "closed"
    assert [(m, p) for m, p, _ in gh.writes] == [("POST", f"repos/{ops.REPO}/issues/12/comments"), ("PATCH", f"repos/{ops.REPO}/issues/12")]
    assert gh.writes[1][2] == {"state": "closed"}
    quiet = FakeGh()
    assert ops.failure_issue(quiet, "r4", "u", resolved=True) == "nothing" and quiet.writes == []


def test_dry_run_writes_nothing(capsys):
    gh = FakeGh()
    assert ops.failure_issue(gh, "r", "u", dry_run=True) == "created"
    assert gh.writes == [] and "dry run: would POST" in capsys.readouterr().out


def test_gh_api_passes_strings_as_fields_and_structures_as_json(monkeypatch):
    calls = []

    class R:
        returncode, stdout, stderr = 0, '{"ok": 1}', ""

    def fake_run(cmd, **kw):
        calls.append((cmd, kw.get("input")))
        return R()
    monkeypatch.setattr(ops.subprocess, "run", fake_run)
    assert ops.gh_api("POST", "repos/x/issues/1/comments", body="hi", nothing=None) == {"ok": 1}
    assert calls[-1] == (["gh", "api", "-X", "POST", "repos/x/issues/1/comments", "-f", "body=hi"], None)
    ops.gh_api("POST", "repos/x/issues", title="t", labels=["l"])
    cmd, stdin = calls[-1]
    assert cmd == ["gh", "api", "-X", "POST", "repos/x/issues", "--input", "-"] and json.loads(stdin) == {"title": "t", "labels": ["l"]}
    R.returncode, R.stderr = 1, "HTTP 403"
    with pytest.raises(RuntimeError, match="403"):
        ops.gh_api("GET", "repos/x")


# ---------------------------------------------------------------------------
# reminders

def pr(number, ref, days_old):
    return {"number": number, "head": {"ref": ref}, "created_at": (NOW - dt.timedelta(days=days_old)).strftime("%Y-%m-%dT%H:%M:%SZ")}


def test_reminder_only_for_old_harvest_prs_without_a_recent_reminder():
    old_reminder = {"body": f"{ops.REMINDER_MARK}\nping", "created_at": (NOW - dt.timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    fresh_reminder = dict(old_reminder, created_at=(NOW - dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    gh = FakeGh({
        f"repos/{ops.REPO}/pulls?state=open": [pr(1, "harvest/20261001T0600", 14), pr(2, "harvest/20261012T0600", 3),
                                               pr(3, "ticket-08-map", 30), pr(4, "harvest/20260920T0600", 25), pr(5, "harvest/20260901T0600", 44)],
        f"repos/{ops.REPO}/issues/4/comments": [fresh_reminder, {"body": "human comment", "created_at": old_reminder["created_at"]}],
        f"repos/{ops.REPO}/issues/5/comments": [old_reminder],
    })
    assert ops.remind(gh, "Angelo-M-SCS", days=7, now=NOW) == [1, 5]
    for m, path, f in gh.writes:
        assert m == "POST" and path.endswith("/comments") and "@Angelo-M-SCS" in f["body"] and ops.REMINDER_MARK in f["body"]
    assert "docs/review/20261001T0600.html" in gh.writes[0][2]["body"] and "14 days" in gh.writes[0][2]["body"]


def test_reminder_dry_run_lists_without_commenting(capsys):
    gh = FakeGh({f"repos/{ops.REPO}/pulls?state=open": [pr(1, "harvest/x", 10)]})
    assert ops.remind(gh, "m", now=NOW, dry_run=True) == [1]
    assert gh.writes == [] and "dry run" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# state branch, against a bare remote

@pytest.fixture
def remote_and_clone(tmp_path, monkeypatch):
    for k, v in dict(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                     GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com").items():
        monkeypatch.setenv(k, v)
    env = dict(os.environ)
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True, env=env)
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True, env=env)
    (seed / "README.md").write_text("x\n")
    subprocess.run(["git", "-C", str(seed), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(seed), "commit", "-q", "-m", "init"], check=True, env=env)
    subprocess.run(["git", "-C", str(seed), "push", "-q", str(bare), "main"], check=True, env=env)
    a, b = tmp_path / "a", tmp_path / "b"
    for c in (a, b):
        subprocess.run(["git", "clone", "-q", "--depth", "1", str(bare), str(c)], check=True, env=env)  # as actions/checkout does
    return bare, a, b


def test_state_round_trip_through_the_state_branch(remote_and_clone, capsys):
    bare, a, b = remote_and_clone
    assert ops.state_pull(a) is False and not (a / "harvest/state.json").exists()
    (a / "harvest").mkdir()
    (a / "harvest/state.json").write_text(json.dumps({"seen": ["amti:1", "amti:2"]}), encoding="utf-8")
    report = {"documents": 3, "candidates": 2, "duplicates": 0, "input_tokens": 100, "output_tokens": 50,
              "estimated_cost_usd": 0.01, "extractor": "m@prompt-x", "failures": []}
    ops.state_push(a, "r1", report, now=NOW)
    # main is untouched; the branch holds state + log
    assert subprocess.run(["git", "-C", str(a), "branch", "--show-current"], capture_output=True, text=True).stdout.strip() == "main"
    assert not subprocess.run(["git", "-C", str(a), "worktree", "list"], capture_output=True, text=True).stdout.count("\n") > 1
    assert ops.state_pull(b) is True
    assert json.loads((b / "harvest/state.json").read_text()) == {"seen": ["amti:1", "amti:2"]}
    # a second run from the other clone appends to the log, keeping the first line
    (b / "harvest/state.json").write_text(json.dumps({"seen": ["amti:1", "amti:2", "amti:3"]}), encoding="utf-8")
    ops.state_push(b, "r2", None, now=NOW)
    log = subprocess.run(["git", "-C", str(bare), "show", f"{ops.STATE_BRANCH}:runs.jsonl"], capture_output=True, text=True).stdout
    lines = [json.loads(l) for l in log.splitlines()]
    assert [l["run_id"] for l in lines] == ["r1", "r2"] and lines[0]["candidates"] == 2 and lines[0]["estimated_cost_usd"] == 0.01
    assert lines[1]["documents"] is None
    files = subprocess.run(["git", "-C", str(bare), "ls-tree", "--name-only", ops.STATE_BRANCH], capture_output=True, text=True).stdout.split()
    assert sorted(files) == ["README.md", "runs.jsonl", "state.json"]
    assert ops.state_pull(a) and "amti:3" in (a / "harvest/state.json").read_text()


def test_stale_local_state_branch_does_not_block_a_push(remote_and_clone):
    """A failed push leaves a local `harvest-state` branch behind; the next push must still work and clean up."""
    _, a, _ = remote_and_clone
    subprocess.run(["git", "-C", str(a), "branch", ops.STATE_BRANCH], check=True)
    (a / "harvest").mkdir()
    (a / "harvest/state.json").write_text('{"seen": []}', encoding="utf-8")
    ops.state_push(a, "r1", None, now=NOW)
    branches = subprocess.run(["git", "-C", str(a), "branch", "--list", ops.STATE_BRANCH], capture_output=True, text=True).stdout
    assert branches.strip() == "" and ops.state_pull(a)


def test_state_push_without_a_state_file_refuses(remote_and_clone):
    _, a, _ = remote_and_clone
    with pytest.raises(RuntimeError, match="nothing to push"):
        ops.state_push(a, "r")


def test_a_remote_that_cannot_be_asked_is_an_error_not_an_empty_state(remote_and_clone):
    _, a, _ = remote_and_clone
    subprocess.run(["git", "-C", str(a), "remote", "set-url", "origin", str(a.parent / "does-not-exist.git")], check=True)
    with pytest.raises(RuntimeError, match="could not query origin"):
        ops.state_pull(a)
    (a / "harvest").mkdir()
    (a / "harvest/state.json").write_text('{"seen": []}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="could not query origin"):
        ops.state_push(a, "r")


def test_documents_whose_extraction_failed_are_retried_next_run(tmp_path):
    caps = tmp_path / "captures" / "src"
    caps.mkdir(parents=True)
    (caps / "a.json").write_text(json.dumps({"capture_id": "capA", "guid": "guid-a", "text": "x"}), encoding="utf-8")
    (caps / "b.json").write_text(json.dumps({"capture_id": "capB", "guid": "guid-b", "text": "x"}), encoding="utf-8")
    (tmp_path / "captures" / "fetch-report.json").write_text("{}", encoding="utf-8")
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"seen": ["guid-a", "guid-b", "guid-c"]}), encoding="utf-8")
    report = {"failures": [{"capture_id": "capB", "error": "max_tokens"}]}
    assert ops.drop_failed(state, report, tmp_path / "captures") == 1
    assert json.loads(state.read_text())["seen"] == ["guid-a", "guid-c"]
    assert ops.drop_failed(state, {"failures": []}, tmp_path / "captures") == 0
    assert ops.drop_failed(state, report, None) == 0


def test_run_log_records_sources_with_errors():
    line = ops.run_log_line("r", {"documents": 1}, NOW, {"sources": [{"source": "a", "errors": ["x"]}, {"source": "b", "errors": []}]})
    assert line["sources_with_errors"] == ["a"] and line["date"] == "2026-10-15T06:00Z"


def test_cli_state_push_needs_a_run_id(remote_and_clone, monkeypatch):
    _, a, _ = remote_and_clone
    monkeypatch.chdir(a)
    with pytest.raises(SystemExit):
        ops.main(["state", "push"])


def test_harvest_run_stops_when_the_fetch_failed(monkeypatch):
    from pipeline import harvest
    monkeypatch.setattr(harvest, "cmd_fetch", lambda ns: 1)
    monkeypatch.setattr(harvest, "cmd_extract", lambda ns: pytest.fail("extract must not run after a failed fetch"))
    import argparse
    args = argparse.Namespace(run_id="t", since="", only="", registry=None, sleep=0, recordings="", record=False, model="m")
    assert harvest.cmd_run(args) == 1
