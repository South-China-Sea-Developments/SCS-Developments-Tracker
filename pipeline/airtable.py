"""Airtable as an optional review front end (ADR 0004): the candidates of a review pull request are
mirrored into an Airtable table with the same fields and decision options as the review page; the
coder's decisions there are pulled back as the very same decisions file the review page exports,
and applied with `pipeline.queue decide`. Airtable is never read by the loader, the validator or
the site build, and this module is the only one that knows it exists.

Configuration: pipeline/airtable.json  {"enabled": true|false, "base_id": "app...", "table": "Candidates",
"table_id": "tbl...", "interface": "<url of the review interface, for people>", "field_ids": {name: "fld..."}};
the REST client translates the code's internal field names to these ids at the wire (ticket 21: the
base's columns carry readable labels, `LABELS`), falls back to the labels when no ids are configured,
and addresses the table by its id.
The access token is the environment variable AIRTABLE_TOKEN only (a repository secret if a workflow
ever runs the sync; none does today); it never appears in a file. With enabled = false, no base_id or
no token, every command that would call Airtable says so and does nothing; schema, records and
pull --from never call it.

Budget: the free plan allows 1,000 API calls per workspace per month. Records travel ten per call;
every command counts its calls and refuses to start a step that would pass --max-calls.

Usage:
  python -m pipeline.airtable push  --run <run_id> [--pr N]        candidates of the run -> Airtable (idempotent by event id)
  python -m pipeline.airtable pull  --run <run_id> --out decisions.json [--reviewer NAME]
  python -m pipeline.airtable clear --run <run_id>                 remove a decided run's records (keeps the base small)
  python -m pipeline.airtable schema                               print the table's fields as Airtable needs them
  python -m pipeline.airtable records --run <run_id> --out f.json  the push as JSON, without calling Airtable
  python -m pipeline.airtable pull --run <run_id> --from records.json --out decisions.json   decisions from exported records
  python -m pipeline.airtable run-record --run harvest/runs/<run_id> [--pr N] --out run.json   the run's row for the Runs table (ticket 20)

The workbench around the queue (ticket 20, after the maintainer's TPD Updates sheet): besides
`Candidates`, the base has `Runs` (one row per harvest or backfill run, the run log), `Sources` (a
read-only mirror of pipeline/sources.json), `Sidelines` (things seen that do not merit a candidate)
and `Notes` (free text across candidates). Candidates carry `flags` (what the machine noticed; the
reviewer may edit them, so a refresh leaves them alone), `dataset_status` (where the candidate
stands after the decision; refreshed by the sync, never typed) and `run` (a link to its Runs row).
The REST client writes the Candidates table only; the other tables are filled through the
maintainer's Airtable connector from the JSON these commands emit (docs/airtable-workbench.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from pipeline import schema
from pipeline.queue import EDITABLE, read_table, repo_root, review_context

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "pipeline" / "airtable.json"
API = "https://api.airtable.com/v0"
BATCH = 10
DECISIONS = ["undecided", "merge", "new_move", "duplicate", "reject"]
CRITERIA = list(schema.INTENSIFICATION_CRITERIA)
SUBREGION_CHOICES = [f"{i} {n}" for i, n in zip(range(1, 11), schema.SUBREGION_NAMES)]
FLAGS = ["Excerpt not checked", "Excerpt not found", "Source unreachable", "Possible duplicate", "Date approximate",
         "Low confidence", "Type uncertain", "Needs a second source"]
DATASET_STATUSES = ["In review", "Decision recorded", "Pulled into dataset", "Merged", "Published on site", "Closed without change"]
RUN_TYPES = ["Weekly harvest", "Backfill", "Manual", "Catch-up"]
RUN_VERDICTS = ["Pass", "Partial", "Failed", "No candidates"]
REPO_URL = "https://github.com/South-China-Sea-Developments/SCS-Developments-Tracker"
CLAIMANT_COLOURS = {"CN": "redLight2", "VN": "yellowLight2", "PH": "blueLight2", "MY": "greenLight2", "ID": "orangeLight2", "TW": "purpleLight2"}
TYPE_COLOURS = {"declarative": "blueLight2", "demonstrative": "tealLight2", "coercive": "orangeLight2", "force": "redLight2"}
PRECISION_COLOURS = {"day": "greenLight2", "month": "yellowLight2", "year": "orangeLight2"}
SUBREGION_COLOURS = ["grayLight2", "redLight2", "orangeLight2", "yellowLight2", "greenLight2", "tealLight2", "cyanLight2", "blueLight2", "purpleLight2", "pinkLight2"]
DOMAIN_COLOURS = {"domestic": "purpleLight2", "diplomatic": "blueLight2", "physical": "orangeLight2"}
ISSUE_COLOURS = {"military": "redLight2", "administrative": "blueLight2", "energy": "yellowLight2", "fisheries": "tealLight2", "politics": "purpleLight2"}
DYAD_ACTOR_COLOURS = {"C": "redLight2", "V": "yellowLight2", "P": "blueLight2", "M": "greenLight2", "I": "orangeLight2", "R": "purpleLight2"}
DYADS = [a + b for a in "CVPMBIR" for b in "CVPMBIRAU" if a != b]   # actor first; a dyad not listed is typecast into a grey option


def _choices(names, colours=None) -> dict:
    """Select options, coloured when a colour map is given (the base's chips, ticket 21)."""
    if colours is None:
        return {"choices": [{"name": n} for n in names]}
    if isinstance(colours, list):
        return {"choices": [{"name": n, "color": c} for n, c in zip(names, colours)]}
    return {"choices": [{"name": n, "color": colours[n] if n in colours else colours.get(n[0], "grayLight2")} for n in names]}

# One Airtable field per thing the review page shows or asks. Order is the column order.
FIELDS: list[tuple[str, str, dict]] = [
    # identity and context (written by push, read-only for the coder)
    ("event_id", "singleLineText", {}),
    ("run_id", "singleLineText", {}),
    ("pull_request", "number", {"precision": 0}),
    ("claimant", "singleSelect", _choices(list(CLAIMANT_COLOURS), CLAIMANT_COLOURS)),
    ("date_start", "date", {"dateFormat": {"name": "iso"}}),
    ("date_end", "date", {"dateFormat": {"name": "iso"}}),
    ("date_precision", "singleSelect", _choices(schema.DATE_PRECISION, PRECISION_COLOURS)),
    ("location_name", "singleLineText", {}),
    ("location_precision", "singleSelect", {"choices": [{"name": c} for c in schema.LOCATION_PRECISION]}),
    ("subregion", "singleSelect", _choices(SUBREGION_CHOICES, SUBREGION_COLOURS)),
    ("lat", "number", {"precision": 5}),
    ("lon", "number", {"precision": 5}),
    ("summary", "multilineText", {}),
    ("actors", "singleLineText", {}),
    ("sources", "multilineText", {}),
    ("excerpt", "multilineText", {}),
    ("suggested_type", "singleSelect", _choices(schema.TYPE_FLAGS, TYPE_COLOURS)),
    ("suggested_domains", "multipleSelects", _choices(schema.DOMAIN_FLAGS, DOMAIN_COLOURS)),
    ("suggested_issues", "multipleSelects", _choices(schema.ISSUE_FLAGS, ISSUE_COLOURS)),
    ("suggested_dyads", "multipleSelects", _choices(DYADS, DYAD_ACTOR_COLOURS)),
    ("suggestion_reasoning", "multilineText", {}),
    ("machine_note", "multilineText", {}),
    ("possible_duplicate_of", "singleLineText", {}),
    ("previous_year_moves", "multilineText", {}),
    ("same_year_moves", "multilineText", {}),
    # the workbench (ticket 20): what the machine noticed, where the candidate stands, which run made it
    ("flags", "multipleSelects", {"choices": [{"name": c} for c in FLAGS]}),
    ("dataset_status", "singleSelect", {"choices": [{"name": c} for c in DATASET_STATUSES]}),
    ("run", "multipleRecordLinks", {"linkedTableId": "RUNS_TABLE"}),   # resolved from the configuration in table_schema()
    # the decision (the coder's)
    ("decision", "singleSelect", {"choices": [{"name": c} for c in DECISIONS]}),
    ("merge_into_move", "singleLineText", {}),
    ("merge_into_candidate", "singleLineText", {}),
    ("duplicate_of", "singleLineText", {}),
    ("new_type", "singleSelect", _choices(schema.TYPE_FLAGS, TYPE_COLOURS)),
    ("new_criterion", "singleSelect", {"choices": [{"name": c} for c in CRITERIA]}),
    ("new_year", "singleLineText", {}),
    ("new_ongoing_through", "singleLineText", {}),
    ("new_dyads", "singleLineText", {}),
    ("new_domains", "multipleSelects", {"choices": [{"name": c} for c in schema.DOMAIN_FLAGS]}),
    ("new_issues", "multipleSelects", {"choices": [{"name": c} for c in schema.ISSUE_FLAGS]}),
    ("new_subregions", "multipleSelects", {"choices": [{"name": c} for c in SUBREGION_CHOICES]}),
    ("new_description", "multilineText", {}),
    # edits to the event (blank keeps the value)
    ("edit_date_start", "date", {"dateFormat": {"name": "iso"}}),
    ("edit_date_end", "date", {"dateFormat": {"name": "iso"}}),
    ("edit_date_precision", "singleSelect", {"choices": [{"name": c} for c in schema.DATE_PRECISION]}),
    ("edit_location_name", "singleLineText", {}),
    ("edit_subregion", "singleSelect", {"choices": [{"name": c} for c in SUBREGION_CHOICES]}),
    ("edit_lat", "number", {"precision": 5}),
    ("edit_lon", "number", {"precision": 5}),
    ("edit_actors", "singleLineText", {}),
    ("edit_summary", "multilineText", {}),
    ("note", "multilineText", {}),
    ("reviewer", "singleLineText", {}),
]
FIELD_NAMES = [f[0] for f in FIELDS]

# What the columns are called in the base (ticket 21: readable names, as in the maintainer's other
# bases). The code uses the internal names everywhere; the client translates at the wire, by field id
# when the configuration has them (a rename in the base then changes nothing), else by these labels.
LABELS = {
    "event_id": "Event ID", "run_id": "Run ID", "pull_request": "Pull request", "claimant": "Claimant",
    "date_start": "Start date", "date_end": "End date", "date_precision": "Date precision", "location_name": "Location",
    "location_precision": "Location precision", "subregion": "Sub-region", "lat": "Lat", "lon": "Lon", "summary": "Summary",
    "actors": "Actors", "sources": "Sources", "excerpt": "Excerpt", "suggested_type": "Suggested type",
    "suggested_domains": "Suggested domains", "suggested_issues": "Suggested issues", "suggested_dyads": "Suggested dyads",
    "suggestion_reasoning": "Suggestion reasoning", "machine_note": "Machine note", "possible_duplicate_of": "Possible duplicate of",
    "previous_year_moves": "Previous year's moves", "same_year_moves": "Same year's moves",
    "flags": "Flags", "dataset_status": "Dataset status", "run": "Run",
    "decision": "Decision", "merge_into_move": "Merge into move", "merge_into_candidate": "Merge into candidate", "duplicate_of": "Duplicate of",
    "new_type": "New move: type", "new_criterion": "New move: criterion", "new_year": "New move: year",
    "new_ongoing_through": "New move: ongoing through", "new_dyads": "New move: dyads", "new_domains": "New move: domains",
    "new_issues": "New move: issues", "new_subregions": "New move: sub-regions", "new_description": "New move: description",
    "edit_date_start": "Edit: start date", "edit_date_end": "Edit: end date", "edit_date_precision": "Edit: date precision",
    "edit_location_name": "Edit: location", "edit_subregion": "Edit: sub-region", "edit_lat": "Edit: lat", "edit_lon": "Edit: lon",
    "edit_actors": "Edit: actors", "edit_summary": "Edit: summary", "note": "Note", "reviewer": "Reviewer",
}
LABEL_TO_NAME = {v: k for k, v in LABELS.items()}
CODER_FIELDS = FIELD_NAMES[FIELD_NAMES.index("decision"):]


# ---------------------------------------------------------------------------
# configuration

def load_config(path: Path | None = None) -> dict:
    """The configuration file's values over the defaults; a missing file means disabled."""
    path = path or CONFIG
    cfg = {"enabled": False, "base_id": "", "table": "Candidates"}
    if path.exists():
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    return cfg


def why_disabled(cfg: dict, token: str | None) -> str:
    """'' when the sync may run; otherwise the reason, for the command to print and exit 0."""
    if not cfg.get("enabled"):
        return "Airtable sync is disabled in pipeline/airtable.json"
    if not cfg.get("base_id"):
        return "pipeline/airtable.json has no base_id"
    if not token:
        return "AIRTABLE_TOKEN is not set"
    return ""


# ---------------------------------------------------------------------------
# the client and its counted calls

def run_filter(run_id: str) -> str:
    """The Airtable formula selecting one run's records, by the column's label in the base; a quote in
    the id is escaped, not a break-out."""
    return "{" + LABELS["run_id"] + "} = '" + run_id.replace("\\", "\\\\").replace("'", "\\'") + "'"


class Client:
    """Airtable REST, ten records a call, every call counted. Raises RuntimeError on HTTP and network
    errors. `table` may be the table's id (preferred: survives a rename) or its name."""

    def __init__(self, token: str, base_id: str, table: str, max_calls: int = 200, field_ids: dict[str, str] | None = None):
        self.token, self.base_id, self.table, self.max_calls = token, base_id, table, max_calls
        self.calls = 0
        self.field_ids = dict(field_ids or {})
        self._names = {v: k for k, v in self.field_ids.items()}

    # the wire speaks field ids (or, without them, the internal names); the code speaks internal names
    def wire(self, name: str) -> str:
        return self.field_ids.get(name) or LABELS.get(name, name)

    def unwire(self, key: str) -> str:
        return self._names.get(key) or LABEL_TO_NAME.get(key, key)

    def _out(self, fields: dict) -> dict:
        return {self.wire(k): v for k, v in fields.items()}

    def _in(self, record: dict) -> dict:
        return dict(record, fields={self.unwire(k): v for k, v in record.get("fields", {}).items()})

    def _check(self, n: int = 1) -> None:
        if self.calls + n > self.max_calls:
            raise RuntimeError(f"would exceed --max-calls {self.max_calls} ({self.calls} made, {n} more needed); stopping before the budget")

    def _request(self, method: str, path: str = "", params: dict | None = None, body: dict | None = None) -> dict:
        self._check()
        url = f"{API}/{self.base_id}/{urllib.parse.quote(self.table, safe='')}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Airtable {method} {path or '/'}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"Airtable {method} {path or '/'}: {e.reason}") from None

    def list(self, filter_formula: str = "") -> list[dict]:
        out, offset = [], None
        while True:
            params: dict = {"pageSize": 100}
            if self.field_ids:
                params["returnFieldsByFieldId"] = "true"
            if filter_formula:
                params["filterByFormula"] = filter_formula
            if offset:
                params["offset"] = offset
            page = self._request("GET", params=params)
            out += [self._in(r) for r in page.get("records", [])]
            offset = page.get("offset")
            if not offset:
                return out

    @staticmethod
    def batches(n: int) -> int:
        return (n + BATCH - 1) // BATCH

    def create(self, records: list[dict]) -> list[dict]:
        self._check(self.batches(len(records)))
        out = []
        for i in range(0, len(records), BATCH):
            page = self._request("POST", body={"records": [{"fields": self._out(r)} for r in records[i:i + BATCH]], "typecast": True,
                                               **({"returnFieldsByFieldId": True} if self.field_ids else {})})
            out += [self._in(r) for r in page.get("records", [])]
        return out

    def update(self, records: list[tuple[str, dict]]) -> None:
        self._check(self.batches(len(records)))
        for i in range(0, len(records), BATCH):
            self._request("PATCH", body={"records": [{"id": rid, "fields": self._out(f)} for rid, f in records[i:i + BATCH]], "typecast": True})

    def delete(self, ids: list[str]) -> None:
        self._check(self.batches(len(ids)))
        for i in range(0, len(ids), BATCH):
            self._request("DELETE", params={"records[]": ids[i:i + BATCH]})


# ---------------------------------------------------------------------------
# candidates -> records

def _num(s: str) -> float | None:
    """A CSV number cell as a number; blank or unparsable is None (the cell stays empty in Airtable)."""
    try:
        return float(s) if s not in ("", None) else None
    except ValueError:
        return None


def _subregion_choice(n: str) -> str:
    """The select option for a sub-region number ("4" -> "4 Central-East"); blank when not 1-10."""
    return SUBREGION_CHOICES[int(n) - 1] if n and n.isdigit() and 1 <= int(n) <= 10 else ""


def _moves_text(moves: list[dict]) -> str:
    """The claimant's moves of a year as the review page lists them, one per line."""
    return "\n".join(f"{m['move_id']} [{', '.join(m['types'])}]{' pending' if m['status'] != 'accepted' else ''}: {m['description']}" for m in moves)


def flags_for(e: dict) -> list[str]:
    """The flags the import's notes and the suggestion imply, in FLAGS order: the machine note says
    whether the excerpt was checked, found, or the source unreachable, and whether a near match
    exists; month or year precision is an approximate date; the reasoning's confidence tag."""
    note = e.get("review_note") or ""
    found = set()
    if "could not be fetched" in note:
        found |= {"Source unreachable", "Excerpt not checked"}
    elif "not checked" in note:
        found.add("Excerpt not checked")
    if "not found verbatim" in note:
        found.add("Excerpt not found")
    if "Possible duplicate" in note:
        found.add("Possible duplicate")
    if (e.get("date_precision") or "") in ("month", "year"):
        found.add("Date approximate")
    if "[confidence: low]" in (e.get("suggestion_reasoning") or ""):
        found.add("Low confidence")
    return [f for f in FLAGS if f in found]


def records_for_run(data_dir: Path, run_id: str, pr: int | None = None, run_record: str | None = None) -> list[dict]:
    """One Airtable record per candidate of the run: the review page's context fields, and the coder's
    fields prefilled as the page prefills them (decision undecided; the new move's type, dyads, domains,
    issues and sub-region from the suggestion and the event; duplicate_of from the machine's flag).
    Year and description are left blank: `decide` defaults them to the event's year and summary, as the
    page does. Only `push` on a new record writes the coder's fields; a refresh never touches them."""
    ctx = review_context(data_dir, run_id=run_id)
    out = []
    for it in ctx["items"]:
        e = it["event"]
        srcs = it["sources"]
        dup = it["duplicate_of"]["event_id"] if it.get("duplicate_of") else ""
        rec = {
            "event_id": e["event_id"], "run_id": run_id, "pull_request": pr, "claimant": e["claimant"],
            "date_start": e["date_start"] or None, "date_end": e["date_end"] or None, "date_precision": e["date_precision"] or None,
            "location_name": e["location_name"], "location_precision": e["location_precision"] or None,
            "subregion": _subregion_choice(e["subregion"]) or None, "lat": _num(e["lat"]), "lon": _num(e["lon"]),
            "summary": e["summary"], "actors": e["actors"],
            "sources": "\n".join(" ".join(x for x in (s["title"] or s["url"], "—", s["publisher"], s["pub_date"]) if x) + "\n" + s["url"] for s in srcs),
            "excerpt": "\n\n".join(s["excerpt"] for s in srcs if s["excerpt"]),
            "suggested_type": e["suggested_type"] or None, "suggested_domains": e["suggested_domains"].split() or None,
            "suggested_issues": e["suggested_issues"].split() or None, "suggested_dyads": e["suggested_dyads"].split() or None,
            "suggestion_reasoning": e["suggestion_reasoning"], "machine_note": e["review_note"],
            "possible_duplicate_of": dup,
            "flags": flags_for(e) or None, "dataset_status": "In review", "run": [run_record] if run_record else None,
            "previous_year_moves": _moves_text(it["previous_year_moves"]), "same_year_moves": _moves_text(it["same_year_moves"]),
            "decision": "undecided", "duplicate_of": dup,
            "new_type": e["suggested_type"] or None, "new_dyads": e["suggested_dyads"],
            "new_domains": e["suggested_domains"].split() or None, "new_issues": e["suggested_issues"].split() or None,
            "new_subregions": [_subregion_choice(e["subregion"])] if _subregion_choice(e["subregion"]) else None,
        }
        out.append({k: v for k, v in rec.items() if v not in (None, "")})
    return out


# A refresh rewrites the context columns, except what is set once at creation and then owned by the
# reviewer or the workflow: the flags, the run link, and the dataset status (which moves on by hand
# until a sync with a token moves it).
SET_ONCE = ("flags", "run", "dataset_status")
CONTEXT_FIELDS = [n for n in FIELD_NAMES if n not in CODER_FIELDS and n not in SET_ONCE]


# ---------------------------------------------------------------------------
# the run log (ticket 20): one row per run, from harvest/runs/<run_id>/run.json and the candidates

def run_type(run_id: str) -> str:
    """Weekly harvests are named by their timestamp, backfill chunks by claimant and period;
    anything else was compiled by hand. "Catch-up" is chosen by the reviewer, never derived."""
    if re.fullmatch(r"\d{8}T\d{4}", run_id):
        return "Weekly harvest"
    if re.fullmatch(r"[A-Z]{2}-\d{4}(-\d{4}|s|-[A-Za-z]+\d{4})?", run_id):
        return "Backfill"
    return "Manual"


def run_date(run_id: str, fallback: str = "") -> str:
    """The run's date: the YYYYMMDD in the id (20261102T0724, manual-20261018-…), else the date given
    (the run.json's finished_at), else today (a backfill chunk is dated by its import)."""
    m = re.search(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)", run_id)
    if m:
        return "-".join(m.groups())
    return fallback[:10] if fallback else dt.date.today().isoformat()


def run_record(run_dir: Path, data_dir: Path, pr: int | None = None, notes: str = "") -> dict:
    """The Runs row: counts from run.json, the excerpt checks and duplicate flags from the run's
    candidates, the sources that failed, the review PR. `notes` is what the compiler or the run
    wants the reviewer to look at."""
    report = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    run_id = report["run_id"]
    ctx = review_context(data_dir, run_id=run_id)
    events = [it["event"] for it in ctx["items"]]
    notes_ = [e.get("review_note") or "" for e in events]
    not_found = sum("not found verbatim" in n for n in notes_)
    unchecked = sum(("not checked" in n or "could not be fetched" in n) and "not found verbatim" not in n for n in notes_)
    verified = len(events) - not_found - unchecked
    failures = report.get("failures") or []
    if isinstance(failures, list):
        failed_sources = sorted({f.get("source_id") or f.get("source") or "?" for f in failures if "deferred" not in (f.get("error") or "")})
        n_fail = len([f for f in failures if "deferred" not in (f.get("error") or "")])
    else:
        failed_sources, n_fail = [], int(failures)
    dates = sorted(e["date_start"] for e in events if e.get("date_start"))
    claimants = sorted({e["claimant"] for e in events})
    scope = ", ".join(ctx["claimants"].get(c, c) for c in claimants)
    if dates:
        scope += f" {dates[0][:4]}" + (f"–{dates[-1][:4]}" if dates[-1][:4] != dates[0][:4] else "")
    if not events and n_fail:
        verdict = "Failed"
    elif not events:
        verdict = "No candidates"
    elif n_fail:
        verdict = "Partial"
    else:
        verdict = "Pass"
    rec = {
        "run_id": run_id, "date": run_date(run_id, report.get("finished_at", "")), "type": run_type(run_id), "scope": scope,
        "verdict": verdict, "documents": report.get("documents"), "candidates": len(events),
        "possible_duplicates": sum("Possible duplicate" in n for n in notes_), "failures": n_fail,
        "excerpts_verified": verified, "excerpts_unchecked": unchecked, "excerpts_not_found": not_found,
        "review_pr": pr, "review_pr_url": f"{REPO_URL}/pull/{pr}" if pr else None,
        "extractor": report.get("extractor", ""), "unreachable_sources": "\n".join(failed_sources) or None,
        "what_to_look_at": notes or None,
    }
    return {k: v for k, v in rec.items() if v not in (None, "")}


# ---------------------------------------------------------------------------
# records -> decisions (the review page's export shape, exactly)

def _sub_number(choice: str) -> str:
    """The sub-region number of a select option ("4 Central-East" -> "4")."""
    return choice.split(" ", 1)[0] if choice else ""


def _plain(v):
    """Airtable's REST API returns select values as names; its other clients return {id, name}
    objects. The decisions must not depend on which route the records came by."""
    if isinstance(v, dict):
        return v.get("name", "")
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


def normalise_record(r: dict, field_ids: dict[str, str] | None = None) -> dict:
    """One record's fields keyed by field name, with plain values, whatever the export shape:
    {"fields": {name: value}} (REST), {"cellValuesByFieldId": {id: value}} (other clients, needs
    the name->id map from the configuration), or a bare {name: value} dict."""
    names = {v: k for k, v in (field_ids or {}).items()}
    raw = r["cellValuesByFieldId"] if "cellValuesByFieldId" in r else r.get("fields", r)
    # keys may be field ids, the base's labels or the internal names, depending on the export
    return {names.get(k) or LABEL_TO_NAME.get(k, k): _plain(v) for k, v in raw.items()}


def _same(col: str, edited, shown) -> bool:
    """Whether an edit column repeats the value the record shows, so there is nothing to change."""
    if col == "subregion":
        return _sub_number(edited or "") == _sub_number(shown or "")
    if col in ("lat", "lon"):
        return _num(str(edited)) == _num(str(shown)) if shown not in (None, "") else False
    return str(edited).strip() == str(shown or "").strip()


def decisions_from_records(records: list[dict], reviewer: str = "", field_ids: dict[str, str] | None = None,
                           run_id: str | None = None) -> dict:
    """The decisions file `pipeline.queue decide` reads, from the coder's fields. Records left
    'undecided', and records of other runs when run_id is given, are skipped; a blank edit field, or
    one repeating the value shown, keeps the event's value, as on the page. Decisions come out in
    event-id order; `apply_decisions` orders them by the events file anyway."""
    decisions = []
    reviewers = set()
    for r in records:
        f = normalise_record(r, field_ids)
        if run_id is not None and f.get("run_id") != run_id:
            continue
        action = f.get("decision") or "undecided"
        if action == "undecided":
            continue
        if not f.get("event_id"):
            raise ValueError(f"record {r.get('id', '?')} has a decision ({action}) but no event_id; only rows the sync created can be decided")
        d: dict[str, Any] = {"event_id": f["event_id"], "action": action, "note": (f.get("note") or "").strip()}
        if f.get("reviewer"):
            reviewers.add(f["reviewer"].strip())
        if action == "merge":
            if f.get("merge_into_candidate"):
                d["move_of_event"] = f["merge_into_candidate"].strip()
            else:
                d["move_id"] = (f.get("merge_into_move") or "").strip()
        if action == "duplicate":
            d["duplicate_of"] = (f.get("duplicate_of") or "").strip()
        if action == "new_move":
            d["new_move"] = {
                "type": f.get("new_type") or "", "intensification_criterion": f.get("new_criterion") or "",
                "year": (f.get("new_year") or "").strip(), "ongoing_through": (f.get("new_ongoing_through") or "").strip(),
                "dyads": (f.get("new_dyads") or "").split(), "domains": list(f.get("new_domains") or []), "issues": list(f.get("new_issues") or []),
                "subregions": [_sub_number(c) for c in (f.get("new_subregions") or [])], "description": (f.get("new_description") or "").strip(),
            }
        if action in ("merge", "new_move", "duplicate"):
            edits = {}
            for col in EDITABLE:
                v = f.get(f"edit_{col}")
                if v in (None, "") or _same(col, v, f.get(col)):
                    continue
                if col == "subregion":
                    v = _sub_number(v)
                edits[col] = str(v).strip()
            if edits:
                d["edits"] = edits
        decisions.append(d)
    decisions.sort(key=lambda d: d["event_id"])          # table order is not meaningful; the file is deterministic
    out = {"decisions": decisions}
    name = reviewer or (reviewers.pop() if len(reviewers) == 1 else "")
    if name:
        out["reviewer"] = name
    return out


# ---------------------------------------------------------------------------
# commands

def push(client: Client, records: list[dict], run_id: str) -> dict:
    """Create the run's records that are not yet there; refresh every context field of those that
    are (a field now blank is blanked), without touching the coder's fields. Idempotent. The whole
    push is checked against the budget before anything is sent."""
    existing = {r["fields"].get("event_id"): r["id"] for r in client.list(run_filter(run_id))}
    new = [r for r in records if r["event_id"] not in existing]
    upd = [(existing[r["event_id"]], {k: r.get(k) for k in CONTEXT_FIELDS}) for r in records if r["event_id"] in existing]
    client._check(client.batches(len(new)) + client.batches(len(upd)))
    if new:
        client.create(new)
    if upd:
        client.update(upd)
    return {"created": len(new), "updated": len(upd), "calls": client.calls}


def pull(client: Client, run_id: str, reviewer: str = "") -> dict:
    """The run's decisions as the file `queue decide` reads (see decisions_from_records)."""
    return decisions_from_records(client.list(run_filter(run_id)), reviewer, run_id=run_id)


def clear(client: Client, run_id: str) -> int:
    """Delete the run's records (after its pull request is merged; the files are the record)."""
    ids = [r["id"] for r in client.list(run_filter(run_id))]
    if ids:
        client.delete(ids)
    return len(ids)


def table_schema() -> dict:
    """The Candidates table as Airtable's schema API wants it (`name` is the base's label; `internal`
    the code's name); the live base was created from an earlier version of it and updated by hand since."""
    cfg = load_config()
    fields = []
    for n, t, o in FIELDS:
        if n == "run":
            o = {"linkedTableId": cfg.get("runs_table_id", "")}
        fields.append({"name": LABELS[n], "internal": n, "type": t, **({"options": o} if o else {})})
    return {"name": cfg.get("table", "Candidates"), "fields": fields}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("push", "pull", "clear", "records"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
        s.add_argument("--data", type=Path, default=None)
        if name != "records":
            s.add_argument("--max-calls", type=int, default=200)
        if name in ("push", "records"):
            s.add_argument("--pr", type=int, default=None)
            s.add_argument("--run-record", default=None, help="the Runs table record id to link the candidates to (rec...)")
        if name in ("pull", "records"):
            s.add_argument("--out", type=Path, required=True)
        if name == "pull":
            s.add_argument("--reviewer", default="")
            s.add_argument("--from", dest="from_file", type=Path, default=None, help="records exported from Airtable as JSON, instead of calling it")
    sub.add_parser("schema")
    rr = sub.add_parser("run-record")
    rr.add_argument("--run", required=True, type=Path, help="the run folder, harvest/runs/<run_id>")
    rr.add_argument("--data", type=Path, default=None)
    rr.add_argument("--pr", type=int, default=None)
    rr.add_argument("--notes", default="", help="what the reviewer should look at")
    rr.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    if a.cmd == "run-record":
        rec = run_record(a.run, a.data or repo_root() / "data", a.pr, a.notes)
        a.out.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"run record for {rec['run_id']} -> {a.out} (nothing sent)")
        return 0
    if a.cmd == "schema":
        print(json.dumps(table_schema(), indent=1))
        return 0
    data_dir = a.data or repo_root() / "data"
    if a.cmd == "records":
        recs = records_for_run(data_dir, a.run, a.pr, a.run_record)
        a.out.write_text(json.dumps(recs, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{len(recs)} record(s) -> {a.out} (nothing sent)")
        return 0
    if a.cmd == "pull" and a.from_file:
        exported = json.loads(a.from_file.read_text(encoding="utf-8"))
        if isinstance(exported, dict):
            exported = exported.get("records", [])
        d = decisions_from_records(exported, a.reviewer, load_config().get("field_ids"), run_id=a.run)
        a.out.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{len(d['decisions'])} decision(s) -> {a.out}")
        return 0
    cfg = load_config()
    token = os.environ.get("AIRTABLE_TOKEN")
    reason = why_disabled(cfg, token)
    if reason:
        print(f"nothing done: {reason}")
        return 0
    client = Client(token, cfg["base_id"], cfg.get("table_id") or cfg["table"], a.max_calls, cfg.get("field_ids"))
    if a.cmd == "push":
        res = push(client, records_for_run(data_dir, a.run, a.pr, a.run_record), a.run)
        print(f"pushed run {a.run}: {res['created']} created, {res['updated']} refreshed, {res['calls']} API call(s)")
    elif a.cmd == "pull":
        d = pull(client, a.run, a.reviewer)
        a.out.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{len(d['decisions'])} decision(s) -> {a.out}; {client.calls} API call(s). Apply with: python -m pipeline.queue decide {a.out}")
    elif a.cmd == "clear":
        n = clear(client, a.run)
        print(f"removed {n} record(s) of run {a.run}; {client.calls} API call(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
