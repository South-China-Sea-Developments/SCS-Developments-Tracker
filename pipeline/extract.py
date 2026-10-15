"""Turn captured documents into candidate events with suggested MATS coding.

The model is reached through LLMClient. AnthropicClient talks to the API; RecordedClient replays
responses saved under a hash of the exact prompt, so tests run offline and a live run can be
re-played; RecordingClient wraps a live client and saves what it returns.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from pipeline import schema

ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "pipeline" / "prompts" / "extract_events.md"

# USD per million tokens, used only for the cost estimate written into run.json.
PRICES = {"claude-sonnet-5-5": (3.0, 15.0), "claude-haiku-5-5": (1.0, 5.0), "claude-opus-5-5": (15.0, 75.0)}


def system_prompt() -> str:
    """The instructions part of the committed prompt file (after the '---' separator)."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[1].strip()


def prompt_hash(system: str) -> str:
    return hashlib.sha256(system.encode("utf-8")).hexdigest()[:12]


class LLMClient:
    model = "none"

    def complete(self, system: str, user: str) -> tuple[str, int, int]:
        """Returns (text, input_tokens, output_tokens)."""
        raise NotImplementedError


class AnthropicClient(LLMClient):
    def __init__(self, model: str, max_tokens: int = 4000):
        import anthropic  # imported here so the rest of the pipeline has no hard dependency

        self._client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> tuple[str, int, int]:
        r = self._client.messages.create(model=self.model, max_tokens=self.max_tokens, temperature=0,
                                         system=system, messages=[{"role": "user", "content": user}])
        text = "".join(block.text for block in r.content if getattr(block, "type", "") == "text")
        return text, r.usage.input_tokens, r.usage.output_tokens


def _key(system: str, user: str) -> str:
    return hashlib.sha256((system + "\n\x00\n" + user).encode("utf-8")).hexdigest()[:24]


class RecordedClient(LLMClient):
    """Replays saved responses; raises if a prompt has no recording (tests must be complete)."""
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.model = "recorded"

    def complete(self, system: str, user: str) -> tuple[str, int, int]:
        path = self.dir / f"{_key(system, user)}.json"
        if not path.exists():
            raise FileNotFoundError(f"no recorded response for this prompt: {path.name}")
        rec = json.loads(path.read_text(encoding="utf-8"))
        self.model = rec.get("model", "recorded")
        return rec["text"], rec.get("input_tokens", 0), rec.get("output_tokens", 0)


class RecordingClient(LLMClient):
    def __init__(self, inner: LLMClient, directory: Path):
        self.inner, self.dir = inner, Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.model = inner.model

    def complete(self, system: str, user: str) -> tuple[str, int, int]:
        text, i, o = self.inner.complete(system, user)
        rec = {"model": self.inner.model, "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "user_prompt_head": user[:300], "text": text, "input_tokens": i, "output_tokens": o}
        (self.dir / f"{_key(system, user)}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        return text, i, o


def parse_events_json(text: str) -> list[dict]:
    """The model is asked for bare JSON; tolerate code fences and leading prose."""
    t = text.strip()
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    evs = data.get("events", []) if isinstance(data, dict) else []
    return [e for e in evs if isinstance(e, dict)]


def user_prompt(capture: dict) -> str:
    head = [f"Source: {capture.get('source_name', capture.get('source_id', ''))} ({capture.get('source_id', '')})",
            f"URL: {capture.get('final_url') or capture.get('url', '')}",
            f"Title: {capture.get('title', '')}",
            f"Published: {capture.get('published') or 'unknown'}",
            f"Fetched: {capture.get('fetched_at', '')[:10]}",
            f"Language: {capture.get('language', '')}"]
    return "\n".join(head) + "\n\nDocument:\n" + capture.get("text", "")


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", s.lower()) if w not in _STOP}


_STOP = {"the", "and", "for", "with", "that", "this", "from", "into", "near", "over", "their", "were", "was", "has",
         "have", "had", "its", "are", "after", "before", "about", "sea", "south", "china", "chinese", "philippine",
         "philippines", "vietnam", "vietnamese", "vessel", "vessels", "ship", "ships", "coast", "guard"}


def _overlap(a_start: str, a_end: str, b_start: str, b_end: str, days: int = 3) -> bool:
    try:
        a0, a1 = dt.date.fromisoformat(a_start), dt.date.fromisoformat(a_end)
        b0, b1 = dt.date.fromisoformat(b_start), dt.date.fromisoformat(b_end)
    except ValueError:
        return False
    pad = dt.timedelta(days=days)
    return a0 - pad <= b1 and b0 - pad <= a1


def find_duplicate(candidate: dict, pool: list[dict]) -> str:
    """The event_id of an existing/earlier event this candidate probably duplicates, or ''."""
    ct = _tokens(candidate.get("summary", ""))
    loc = (candidate.get("location_name") or "").strip().lower()
    for e in pool:
        if e.get("claimant") != candidate.get("claimant") or e.get("event_id") == candidate.get("event_id"):
            continue
        if not _overlap(candidate.get("date_start", ""), candidate.get("date_end", ""), e.get("date_start", ""), e.get("date_end", "")):
            continue
        et = _tokens(e.get("summary", ""))
        jacc = len(ct & et) / len(ct | et) if (ct | et) else 0.0
        same_loc = bool(loc) and loc == (e.get("location_name") or "").strip().lower()
        if jacc >= 0.4 or (same_loc and jacc >= 0.15):
            return e["event_id"]
    return ""


class Extractor:
    DEFAULT_MODEL = "claude-sonnet-5-5"
    VALID_CLAIMANTS = set(schema.CLAIMANT_CODES)

    def __init__(self, client: LLMClient, run_id: str):
        self.client = client
        self.run_id = run_id
        self.system = system_prompt()
        self.extractor_id = f"{client.model}@prompt-{prompt_hash(self.system)}"

    def _event_id(self, capture: dict, ev: dict, n: int) -> str:
        raw = f"{capture.get('guid') or capture.get('url')}|{ev.get('claimant')}|{ev.get('date_start')}|{n}"
        return "ev-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]

    def _normalise(self, capture: dict, ev: dict, n: int) -> tuple[dict, dict] | None:
        claimant = str(ev.get("claimant", "")).upper().strip()
        if claimant not in self.VALID_CLAIMANTS:
            return None
        start, end = str(ev.get("date_start", "")).strip(), str(ev.get("date_end", "") or ev.get("date_start", "")).strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", start) or not re.match(r"^\d{4}-\d{2}-\d{2}$", end):
            return None
        precision = ev.get("date_precision", "day")
        if precision not in schema.DATE_PRECISION:
            precision = "day" if start == end else "month"
        sub = str(ev.get("subregion", "") or "").strip()
        sub = sub if sub in {str(i) for i in range(1, 11)} else ""
        suggested_type = ev.get("suggested_type", "")
        suggested_type = suggested_type if suggested_type in schema.TYPE_FLAGS else ""
        domains = [d for d in (ev.get("suggested_domains") or []) if d in schema.DOMAIN_FLAGS]
        issues = [i for i in (ev.get("suggested_issues") or []) if i in schema.ISSUE_FLAGS]
        dyads = [d for d in (ev.get("suggested_dyads") or []) if isinstance(d, str) and 1 <= len(d) <= 2 and set(d) <= schema.DYAD_LETTERS]
        eid = self._event_id(capture, ev, n)
        event = {c: "" for c in schema.TABLES["events"]}
        event.update(
            event_id=eid, move_id="", claimant=claimant, date_start=start, date_end=end, date_precision=precision,
            lat=str(ev.get("lat", "") or ""), lon=str(ev.get("lon", "") or ""),
            location_name=str(ev.get("location_name", "") or "").strip(),
            location_precision="feature" if ev.get("location_name") else "unknown", subregion=sub,
            summary=str(ev.get("summary", "")).strip(), actors=str(ev.get("actors", "") or "").strip(),
            status="candidate", harvest_run_id=self.run_id, extractor=self.extractor_id,
            suggested_move_id="", suggested_type=suggested_type, suggested_domains=" ".join(domains),
            suggested_issues=" ".join(issues), suggested_dyads=" ".join(dyads),
            suggestion_reasoning=(str(ev.get("reasoning", "")).strip() + f" [confidence: {ev.get('confidence', 'unstated')}]").strip(),
            reviewer="", review_date="", review_note="",
        )
        source = {c: "" for c in schema.TABLES["sources"]}
        source.update(
            source_id=f"{eid}-S01", event_id=eid, url=capture.get("final_url") or capture.get("url", ""),
            title=capture.get("title", ""), publisher=capture.get("source_name", ""), pub_date=capture.get("published", ""),
            language=capture.get("language", ""), accessed_date=capture.get("fetched_at", "")[:10], archive_url="",
            excerpt=str(ev.get("excerpt", ""))[:400],
        )
        return event, source

    def extract_one(self, capture: dict) -> tuple[list[dict], list[dict], int, int]:
        text, i, o = self.client.complete(self.system, user_prompt(capture))
        events, sources = [], []
        for n, ev in enumerate(parse_events_json(text), start=1):
            norm = self._normalise(capture, ev, n)
            if norm:
                events.append(norm[0]); sources.append(norm[1])
        return events, sources, i, o

    def extract_all(self, captures: list[dict], existing_events: list[dict] | None = None) -> tuple[list[dict], list[dict], dict]:
        events, sources, failures = [], [], []
        in_tok = out_tok = 0
        for cap in captures:
            try:
                ev, so, i, o = self.extract_one(cap)
            except Exception as e:  # one bad document must not sink the run
                failures.append({"capture_id": cap.get("capture_id"), "url": cap.get("url"), "error": str(e)[:300]})
                continue
            in_tok += i; out_tok += o
            events.extend(ev); sources.extend(so)
        pool = list(existing_events or [])
        dup = 0
        for e in events:
            d = find_duplicate(e, pool)
            if d:
                e["review_note"] = f"Possible duplicate of {d}."
                dup += 1
            pool.append(e)
        price = PRICES.get(self.client.model, (0.0, 0.0))
        report = {"run_id": self.run_id, "extractor": self.extractor_id, "model": self.client.model,
                  "captures": len(captures), "documents": len(captures), "candidates": len(events), "duplicates": dup,
                  "input_tokens": in_tok, "output_tokens": out_tok,
                  "estimated_cost_usd": (in_tok * price[0] + out_tok * price[1]) / 1e6, "failures": failures,
                  "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        return events, sources, report
