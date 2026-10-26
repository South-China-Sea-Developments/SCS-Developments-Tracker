"""Ticket 14: extraction without an API key. Prompts written as files and answered by any route
yield the same candidates as a direct extraction (seam 2, on the fixtures); the relevance filter
and the document cap are unit-tested; the "waiting for extraction" issue is tested on the fake
GitHub like the failure issue."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from pipeline import extract, harvest, ops, relevance
from tests.conftest import ROOT
from tests.test_ops import FakeGh

FIX = ROOT / "tests/fixtures/harvest"


def read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# prompts as files

def test_prompts_answered_from_the_recordings_extract_to_the_same_candidates(tmp_path):
    direct = tmp_path / "direct"
    assert harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(direct),
                         "--recordings", str(FIX / "recordings"), "--run-id", "fixture"]) == 0
    prompts = tmp_path / "prompts"
    assert harvest.main(["prompts", "--captures", str(FIX / "captures"), "--out", str(prompts), "--all"]) == 0
    index = json.loads((prompts / "index.json").read_text(encoding="utf-8"))
    assert (prompts / "system.md").read_text(encoding="utf-8") == extract.system_prompt()
    assert len(index["documents"]) == 7 and all((prompts / "prompts" / f"{d['key']}.md").exists() for d in index["documents"])
    # "answering" each prompt: the recorded response for that key, written in the recorded format
    answers = tmp_path / "answers"
    answers.mkdir()
    for d in index["documents"]:
        rec = json.loads((FIX / "recordings" / f"{d['key']}.json").read_text(encoding="utf-8"))
        (answers / f"{d['key']}.json").write_text(json.dumps({"model": rec["model"], "text": rec["text"], "stop_reason": "end_turn"}), encoding="utf-8")
    via = tmp_path / "via"
    assert harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(via),
                         "--recordings", str(answers), "--prompts", str(prompts), "--run-id", "fixture"]) == 0
    assert read(via / "candidates.csv") == read(direct / "candidates.csv")
    assert read(via / "sources.csv") == read(direct / "sources.csv")
    report = json.loads((via / "run.json").read_text(encoding="utf-8"))
    assert report["candidates"] == 5 and report["failures"] == [] and report["irrelevant"] == 0 and report["deferred"] == 0
    assert report["input_tokens"] == 0 and report["estimated_cost_usd"] is None     # an answer without counts costs "unknown"


def test_the_prompt_key_is_the_recording_key_and_the_user_prompt_is_the_extractors():
    caps = harvest.load_captures(FIX / "captures")
    cap = caps[0]
    key = extract.prompt_key(cap)
    assert key == extract._key(extract.system_prompt(), extract.user_prompt(cap))
    assert (FIX / "recordings" / f"{key}.json").exists()


def test_long_documents_are_cut_at_the_same_place_for_every_route():
    cap = {"source_id": "x", "title": "t", "text": "word " * 10_000}
    u = extract.user_prompt(cap)
    assert len(u) < extract.MAX_DOCUMENT_CHARS + 500 and "[document cut here" in u
    short = extract.user_prompt({"source_id": "x", "title": "t", "text": "short"})
    assert "[document cut here" not in short


def test_unanswered_prompts_are_failures_and_deferred_ones_are_retried(tmp_path):
    prompts = tmp_path / "prompts"
    assert harvest.main(["prompts", "--captures", str(FIX / "captures"), "--out", str(prompts), "--max-documents", "3"]) == 0
    index = json.loads((prompts / "index.json").read_text(encoding="utf-8"))
    assert len(index["documents"]) == 3 and len(index["deferred"]) == 7 - 3 - len(index["irrelevant"])
    # newest first: the three selected are the three latest by publication date
    pub = {c["capture_id"]: c.get("published", "") for c in harvest.load_captures(FIX / "captures")}
    assert min(pub[d["capture_id"]] for d in index["documents"]) >= max(pub[d] for d in index["deferred"])
    answers = tmp_path / "answers"
    answers.mkdir()
    d0 = index["documents"][0]
    rec = json.loads((FIX / "recordings" / f"{d0['key']}.json").read_text(encoding="utf-8"))
    (answers / f"{d0['key']}.json").write_text(json.dumps({"model": "claude-code/claude-sonnet-5-5", "text": rec["text"]}), encoding="utf-8")
    out = tmp_path / "out"
    harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(out), "--recordings", str(answers), "--prompts", str(prompts), "--run-id", "r"])
    report = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert report["documents"] == 7 and report["deferred"] == len(index["deferred"])
    errors = {f["capture_id"]: f["error"] for f in report["failures"]}
    assert all(errors[d] == "deferred: over this run's document cap; fetched again next run" for d in index["deferred"])
    assert sum(1 for e in errors.values() if e.startswith("no answer")) == 2       # the two selected but unanswered
    assert report["extractor"].startswith("claude-code/claude-sonnet-5-5@prompt-")
    # the state mechanism retries every failure, so deferred and unanswered documents come back next run
    state = tmp_path / "state.json"
    caps = harvest.load_captures(FIX / "captures")
    state.write_text(json.dumps({"seen": [c["guid"] for c in caps]}), encoding="utf-8")
    assert ops.drop_failed(state, report, FIX / "captures") == len(report["failures"])


# ---------------------------------------------------------------------------
# relevance

@pytest.mark.parametrize("text, expected", [
    ("The coast guard escorted fishermen near Scarborough Shoal on Monday.", True),
    ("Hai quân Việt Nam tuần tra tại quần đảo Trường Sa.", True),                       # a gazetteer name, Vietnamese
    ("Kapal Bakamla mengusir kapal asing di Laut Natuna Utara.", True),                  # a sea-level term, Indonesian
    ("中国海警在南海巡航。", True),                                                        # CJK term
    ("Malaysia's central bank held its policy rate at 3 per cent.", False),
    ("The Prime Minister opened a new hospital in Sabah.", False),                        # a place, not the sea
    ("", False),
])
def test_relevance_by_term_or_feature(text, expected):
    assert relevance.is_relevant({"title": "", "text": text}) is expected


def test_relevance_looks_at_the_title_too():
    assert relevance.is_relevant({"title": "West Philippine Sea: PCG reports", "text": "Details follow."})


def test_every_fixture_capture_is_relevant():
    caps = harvest.load_captures(FIX / "captures")
    assert all(relevance.is_relevant(c) for c in caps if len(c["text"]) > 100)


def test_select_orders_newest_first_and_caps():
    caps = [{"capture_id": f"c{i}", "published": f"2026-10-{10 + i:02d}", "title": "South China Sea", "text": "x"} for i in range(5)]
    caps.append({"capture_id": "noise", "published": "2026-10-30", "title": "Budget speech", "text": "taxes"})
    sel, irrelevant, deferred = relevance.select(caps, max_documents=2)
    assert [c["capture_id"] for c in sel] == ["c4", "c3"] and irrelevant == ["noise"] and deferred == ["c2", "c1", "c0"]
    sel, irrelevant, deferred = relevance.select(caps, max_documents=0)
    assert len(sel) == 5 and deferred == []


# ---------------------------------------------------------------------------
# the waiting issue

def test_waiting_issue_is_not_a_failure_issue_and_is_closed_by_an_extracting_run():
    gh = FakeGh()
    assert ops.failure_issue(gh, "20261026T0703", "https://ci/run/9", detail="250 documents fetched", kind="waiting") == "created"
    (m, path, f), = gh.writes
    assert f["labels"] == [ops.WAITING_LABEL] and f["title"] == ops.WAITING_TITLE and ops.WAITING_MARK in f["body"] and "250 documents" in f["body"]
    assert "CLAUDE_CODE_OAUTH_TOKEN" in f["body"] and "/harvest-extract" in f["body"]
    # a second waiting run comments; an open failure issue is a different conversation
    open_ = {f"repos/{ops.REPO}/issues?state=open": [{"number": 16, "title": ops.FAILURE_TITLE, "labels": [{"name": ops.FAILURE_LABEL}]},
                                                      {"number": 23, "title": ops.WAITING_TITLE, "labels": [{"name": ops.WAITING_LABEL}]}]}
    gh = FakeGh(open_)
    assert ops.failure_issue(gh, "20261102T0703", "https://ci/run/10", kind="waiting") == "commented"
    assert gh.writes[0][1] == f"repos/{ops.REPO}/issues/23/comments"
    # the next run that extracts closes both
    gh = FakeGh(open_)
    assert ops.failure_issue(gh, "20261109T0703", "https://ci/run/11", resolved=True) == "closed"
    assert {w[1] for w in gh.writes if w[0] == "PATCH"} == {f"repos/{ops.REPO}/issues/16", f"repos/{ops.REPO}/issues/23"}


# ---------------------------------------------------------------------------
# the skill and the workflow agree on the file contract

def test_skill_and_workflow_name_the_same_paths():
    skill = (ROOT / ".claude/skills/harvest-extract/SKILL.md").read_text(encoding="utf-8")
    wf = (ROOT / ".github/workflows/harvest.yml").read_text(encoding="utf-8")
    assert "harvest/prompts/" in skill and "harvest/recordings/" in skill and "index.json" in skill and "system.md" in skill
    assert "anthropics/claude-code-action@v1" in wf and "claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}" in wf
    assert "/harvest-extract" in wf and "id-token: write" in wf
    assert "python -m pipeline.harvest prompts" in wf and "--prompts" in wf
    assert "kind waiting" in wf or "--kind waiting" in wf
