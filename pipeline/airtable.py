"""Airtable as an optional review front end (ADR 0004): the candidates of a review pull request are
mirrored into an Airtable table with the same fields and decision options as the review page; the
coder's decisions there are pulled back as the very same decisions file the review page exports,
and applied with `pipeline.queue decide`. Airtable is never read by the loader, the validator or
the site build, and this module is the only one that knows it exists.

Configuration: pipeline/airtable.json  {"enabled": true|false, "base_id": "app...", "table": "Candidates",
"table_id": "tbl...", "interface": "<url of the review interface, for people>", "field_ids": {name: "fld..."}};
the field ids are only needed to read an export made with another Airtable client (pull --from), the
REST client works by field name and addresses the table by its id.
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
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
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

# One Airtable field per thing the review page shows or asks. Order is the column order.
FIELDS: list[tuple[str, str, dict]] = [
    # identity and context (written by push, read-only for the coder)
    ("event_id", "singleLineText", {}),
    ("run_id", "singleLineText", {}),
    ("pull_request", "number", {"precision": 0}),
    ("claimant", "singleLineText", {}),
    ("date_start", "date", {"dateFormat": {"name": "iso"}}),
    ("date_end", "date", {"dateFormat": {"name": "iso"}}),
    ("date_precision", "singleSelect", {"choices": [{"name": c} for c in schema.DATE_PRECISION]}),
    ("location_name", "singleLineText", {}),
    ("location_precision", "singleSelect", {"choices": [{"name": c} for c in schema.LOCATION_PRECISION]}),
    ("subregion", "singleSelect", {"choices": [{"name": c} for c in SUBREGION_CHOICES]}),
    ("lat", "number", {"precision": 5}),
    ("lon", "number", {"precision": 5}),
    ("summary", "multilineText", {}),
    ("actors", "singleLineText", {}),
    ("sources", "multilineText", {}),
    ("excerpt", "multilineText", {}),
    ("suggested_type", "singleSelect", {"choices": [{"name": c} for c in schema.TYPE_FLAGS]}),
    ("suggested_domains", "singleLineText", {}),
    ("suggested_issues", "singleLineText", {}),
    ("suggested_dyads", "singleLineText", {}),
    ("suggestion_reasoning", "multilineText", {}),
    ("machine_note", "multilineText", {}),
    ("possible_duplicate_of", "singleLineText", {}),
    ("previous_year_moves", "multilineText", {}),
    ("same_year_moves", "multilineText", {}),
    # the decision (the coder's)
    ("decision", "singleSelect", {"choices": [{"name": c} for c in DECISIONS]}),
    ("merge_into_move", "singleLineText", {}),
    ("merge_into_candidate", "singleLineText", {}),
    ("duplicate_of", "singleLineText", {}),
    ("new_type", "singleSelect", {"choices": [{"name": c} for c in schema.TYPE_FLAGS]}),
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
    """The Airtable formula selecting one run's records; a quote in the id is escaped, not a break-out."""
    return "{run_id} = '" + run_id.replace("\\", "\\\\").replace("'", "\\'") + "'"


class Client:
    """Airtable REST, ten records a call, every call counted. Raises RuntimeError on HTTP and network
    errors. `table` may be the table's id (preferred: survives a rename) or its name."""

    def __init__(self, token: str, base_id: str, table: str, max_calls: int = 200):
        self.token, self.base_id, self.table, self.max_calls = token, base_id, table, max_calls
        self.calls = 0

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
            if filter_formula:
                params["filterByFormula"] = filter_formula
            if offset:
                params["offset"] = offset
            page = self._request("GET", params=params)
            out += page.get("records", [])
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
            out += self._request("POST", body={"records": [{"fields": r} for r in records[i:i + BATCH]], "typecast": True}).get("records", [])
        return out

    def update(self, records: list[tuple[str, dict]]) -> None:
        self._check(self.batches(len(records)))
        for i in range(0, len(records), BATCH):
            self._request("PATCH", body={"records": [{"id": rid, "fields": f} for rid, f in records[i:i + BATCH]], "typecast": True})

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


def records_for_run(data_dir: Path, run_id: str, pr: int | None = None) -> list[dict]:
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
            "suggested_type": e["suggested_type"] or None, "suggested_domains": e["suggested_domains"], "suggested_issues": e["suggested_issues"],
            "suggested_dyads": e["suggested_dyads"], "suggestion_reasoning": e["suggestion_reasoning"], "machine_note": e["review_note"],
            "possible_duplicate_of": dup,
            "previous_year_moves": _moves_text(it["previous_year_moves"]), "same_year_moves": _moves_text(it["same_year_moves"]),
            "decision": "undecided", "duplicate_of": dup,
            "new_type": e["suggested_type"] or None, "new_dyads": e["suggested_dyads"],
            "new_domains": e["suggested_domains"].split() or None, "new_issues": e["suggested_issues"].split() or None,
            "new_subregions": [_subregion_choice(e["subregion"])] if _subregion_choice(e["subregion"]) else None,
        }
        out.append({k: v for k, v in rec.items() if v not in (None, "")})
    return out


CONTEXT_FIELDS = [n for n in FIELD_NAMES if n not in CODER_FIELDS]


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
    if "cellValuesByFieldId" in r:
        names = {v: k for k, v in (field_ids or {}).items()}
        raw = {names.get(k, k): v for k, v in r["cellValuesByFieldId"].items()}
    else:
        raw = r.get("fields", r)
    return {k: _plain(v) for k, v in raw.items()}


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
    """The Candidates table as Airtable's schema API wants it; the live base was created from it."""
    return {"name": load_config().get("table", "Candidates"), "fields": [{"name": n, "type": t, **({"options": o} if o else {})} for n, t, o in FIELDS]}


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
        if name in ("pull", "records"):
            s.add_argument("--out", type=Path, required=True)
        if name == "pull":
            s.add_argument("--reviewer", default="")
            s.add_argument("--from", dest="from_file", type=Path, default=None, help="records exported from Airtable as JSON, instead of calling it")
    sub.add_parser("schema")
    a = p.parse_args(argv)
    if a.cmd == "schema":
        print(json.dumps(table_schema(), indent=1))
        return 0
    data_dir = a.data or repo_root() / "data"
    if a.cmd == "records":
        recs = records_for_run(data_dir, a.run, a.pr)
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
    client = Client(token, cfg["base_id"], cfg.get("table_id") or cfg["table"], a.max_calls)
    if a.cmd == "push":
        res = push(client, records_for_run(data_dir, a.run, a.pr), a.run)
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
