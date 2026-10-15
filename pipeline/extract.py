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

# USD per million tokens, used only for the cost estimate written into run.json; unknown model -> cost "unknown".
PRICES = {"claude-sonnet-5-5": (3.0, 15.0), "claude-haiku-5-5": (1.0, 5.0), "claude-opus-5-5": (15.0, 75.0)}
MAX_TEXT_FIELD = 1000


def system_prompt() -> str:
    """The instructions part of the committed prompt file (after the '---' separator)."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[1].strip()


def prompt_hash(system: str) -> str:
    return hashlib.sha256(system.encode("utf-8")).hexdigest()[:12]


class LLMClient:
    model = "none"

    def complete(self, system: str, user: str) -> tuple[str, int, int, str]:
        """Returns (text, input_tokens, output_tokens, stop_reason). stop_reason 'max_tokens' means truncated."""
        raise NotImplementedError


class AnthropicClient(LLMClient):
    def __init__(self, model: str, max_tokens: int = 8000):
        import anthropic  # optional extra: pip install -e ".[llm]"; the API key comes from ANTHROPIC_API_KEY

        self._client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> tuple[str, int, int, str]:
        r = self._client.messages.create(model=self.model, max_tokens=self.max_tokens, temperature=0,
                                         system=system, messages=[{"role": "user", "content": user}])
        text = "".join(block.text for block in r.content if getattr(block, "type", "") == "text")
        return text, r.usage.input_tokens, r.usage.output_tokens, str(r.stop_reason or "")


def _key(system: str, user: str) -> str:
    return hashlib.sha256((system + "\n\x00\n" + user).encode("utf-8")).hexdigest()[:24]


class RecordedClient(LLMClient):
    """Replays saved responses; raises if a prompt has no recording (tests must be complete)."""
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        models = {json.loads(p.read_text(encoding="utf-8")).get("model", "recorded") for p in self.dir.glob("*.json")}
        self.model = sorted(models)[0] if len(models) == 1 else "recorded" if not models else "recorded-mixed"

    def complete(self, system: str, user: str) -> tuple[str, int, int, str]:
        path = self.dir / f"{_key(system, user)}.json"
        if not path.exists():
            raise FileNotFoundError(f"no recorded response for this prompt: {path.name}")
        rec = json.loads(path.read_text(encoding="utf-8"))
        return rec["text"], rec.get("input_tokens", 0), rec.get("output_tokens", 0), rec.get("stop_reason", "end_turn")


class RecordingClient(LLMClient):
    def __init__(self, inner: LLMClient, directory: Path):
        self.inner, self.dir = inner, Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.model = inner.model

    def complete(self, system: str, user: str) -> tuple[str, int, int, str]:
        text, i, o, stop = self.inner.complete(system, user)
        rec = {"model": self.inner.model, "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "user_prompt_head": user[:300], "text": text, "input_tokens": i, "output_tokens": o, "stop_reason": stop}
        (self.dir / f"{_key(system, user)}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        return text, i, o, stop


def parse_events_json(text: str) -> list[dict] | None:
    """The model is asked for bare JSON; tolerate code fences and surrounding prose.
    Returns None when no JSON object with an "events" list can be decoded (a failure, not "no events")."""
    t = text.strip()
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\{", t):
        try:
            data, _ = decoder.raw_decode(t, m.start())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            return [e for e in data["events"] if isinstance(e, dict)]
    return None


def user_prompt(capture: dict) -> str:
    head = [f"Source: {capture.get('source_name', capture.get('source_id', ''))} ({capture.get('source_id', '')})",
            f"URL: {capture.get('final_url') or capture.get('url', '')}",
            f"Title: {capture.get('title', '')}",
            f"Published: {capture.get('published') or 'unknown'}",
            f"Fetched: {capture.get('fetched_at', '')[:10]}",
            f"Language: {capture.get('language', '')}"]
    body = capture.get("text", "").replace("</document>", "</ document>")
    return "\n".join(head) + "\n\n<document>\n" + body + "\n</document>"


_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "\u00a0": " "})


def _canon(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_QUOTES)).strip().lower()


def excerpt_in_text(excerpt: str, text: str) -> bool:
    """Verbatim up to quote style and whitespace."""
    return bool(excerpt.strip()) and _canon(excerpt) in _canon(text)


def _clean_text(v, limit: int = MAX_TEXT_FIELD) -> str:
    s = str(v if v is not None else "").strip()[:limit]
    return ("'" + s) if s[:1] in "=+-@" else s        # never a formula if the CSV is opened in a spreadsheet


def _clean_coord(v, lo: float, hi: float) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return ""
    return f"{f:.4f}" if lo <= f <= hi else ""


def _iso_date(s) -> str:
    try:
        return dt.date.fromisoformat(str(s).strip()).isoformat()
    except (TypeError, ValueError):
        return ""


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


def _loc_tokens(name: str) -> set[str]:
    """'Second Thomas Shoal (Ren'ai Jiao)' and 'Second Thomas Shoal' share tokens; parentheticals are kept as extra tokens."""
    return {w for w in re.findall(r"[a-z]{3,}", name.lower()) if w not in {"the", "island", "islands", "reef", "shoal", "bank", "cay", "waters", "area"}}


def find_duplicate(candidate: dict, pool: list[dict]) -> str:
    """The event_id of an existing/earlier event this candidate probably duplicates, or ''."""
    ct = _tokens(candidate.get("summary", ""))
    cl = _loc_tokens(candidate.get("location_name") or "")
    for e in pool:
        if e.get("claimant") != candidate.get("claimant") or e.get("event_id") == candidate.get("event_id"):
            continue
        if not _overlap(candidate.get("date_start", ""), candidate.get("date_end", ""), e.get("date_start", ""), e.get("date_end", "")):
            continue
        et = _tokens(e.get("summary", ""))
        jacc = len(ct & et) / len(ct | et) if (ct | et) else 0.0
        el = _loc_tokens(e.get("location_name") or "")
        same_loc = bool(cl and el) and bool(cl & el)
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

    def _event_id(self, capture: dict, claimant: str, start: str, n: int) -> str:
        """Deterministic for identical model output; a re-capture of the same document yields the same ids
        (the validator's duplicate-id rule then catches a second import)."""
        raw = f"{capture.get('guid') or capture.get('url')}|{claimant}|{start}|{n}"
        return "ev-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]

    def _normalise(self, capture: dict, ev: dict, n: int) -> tuple[dict, dict] | None:
        claimant = str(ev.get("claimant", "")).upper().strip()
        if claimant not in self.VALID_CLAIMANTS:
            return None
        start = _iso_date(ev.get("date_start"))
        end = _iso_date(ev.get("date_end")) or start
        if not start or end < start:
            return None
        precision = ev.get("date_precision", "")
        if precision not in schema.DATE_PRECISION:
            precision = "day" if start == end else "month"
        sub = str(ev.get("subregion", "") or "").strip()
        sub = sub if sub in {str(i) for i in range(1, 11)} else ""
        suggested_type = ev.get("suggested_type", "")
        suggested_type = suggested_type if suggested_type in schema.TYPE_FLAGS else ""
        domains = [d for d in (ev.get("suggested_domains") or []) if d in schema.DOMAIN_FLAGS]
        issues = [i for i in (ev.get("suggested_issues") or []) if i in schema.ISSUE_FLAGS]
        dyads = [d for d in (ev.get("suggested_dyads") or []) if isinstance(d, str) and 1 <= len(d) <= 2 and set(d) <= schema.DYAD_LETTERS]
        confidence = ev.get("confidence") if ev.get("confidence") in ("high", "medium", "low") else "unstated"
        location = _clean_text(ev.get("location_name"), 200)
        excerpt = _clean_text(ev.get("excerpt"), 400)
        notes = []
        if excerpt and not excerpt_in_text(excerpt, capture.get("text", "")):
            notes.append("Excerpt not found verbatim in the captured text.")
        eid = self._event_id(capture, claimant, start, n)
        event = {c: "" for c in schema.TABLES["events"]}
        event.update(
            event_id=eid, move_id="", claimant=claimant, date_start=start, date_end=end, date_precision=precision,
            lat=_clean_coord(ev.get("lat"), -90, 90), lon=_clean_coord(ev.get("lon"), -180, 180),
            location_name=location, location_precision="feature" if location else "unknown", subregion=sub,
            summary=_clean_text(ev.get("summary")), actors=_clean_text(ev.get("actors"), 300),
            status="candidate", harvest_run_id=self.run_id, extractor=self.extractor_id,
            suggested_move_id="", suggested_type=suggested_type, suggested_domains=" ".join(domains),
            suggested_issues=" ".join(issues), suggested_dyads=" ".join(dyads),
            suggestion_reasoning=(_clean_text(ev.get("reasoning")) + f" [confidence: {confidence}]").strip(),
            reviewer="", review_date="", review_note=" ".join(notes),
        )
        source = {c: "" for c in schema.TABLES["sources"]}
        source.update(
            source_id=f"{eid}-S01", event_id=eid, url=capture.get("final_url") or capture.get("url", ""),
            title=_clean_text(capture.get("title", ""), 300), publisher=capture.get("source_name", ""),
            pub_date=capture.get("published", ""), language=capture.get("language", ""),
            accessed_date=capture.get("fetched_at", "")[:10], archive_url="", excerpt=excerpt,
        )
        return event, source

    def extract_one(self, capture: dict) -> tuple[list[dict], list[dict], int, int]:
        """Raises ValueError when the model's answer is truncated or not the requested JSON."""
        text, i, o, stop = self.client.complete(self.system, user_prompt(capture))
        if stop == "max_tokens":
            raise ValueError(f"response truncated at max_tokens ({o} output tokens)")
        parsed = parse_events_json(text)
        if parsed is None:
            raise ValueError("response is not the requested JSON: " + text[:120].replace("\n", " "))
        events, sources = [], []
        for n, ev in enumerate(parsed, start=1):
            norm = self._normalise(capture, ev, n)
            if norm:
                events.append(norm[0]); sources.append(norm[1])
        return events, sources, i, o

    def extract_all(self, captures: list[dict], existing_events: list[dict] | None = None) -> tuple[list[dict], list[dict], dict]:
        events, sources, failures = [], [], []
        in_tok = out_tok = 0
        by_source: dict[str, dict] = {}
        for cap in captures:
            stat = by_source.setdefault(cap.get("source_id", "?"), {"documents": 0, "candidates": 0, "failures": 0})
            stat["documents"] += 1
            try:
                ev, so, i, o = self.extract_one(cap)
            except Exception as e:  # one bad document must not sink the run, but it is a failure, not "no events"
                failures.append({"capture_id": cap.get("capture_id"), "source_id": cap.get("source_id"), "url": cap.get("url"), "error": str(e)[:300]})
                stat["failures"] += 1
                continue
            in_tok += i; out_tok += o
            stat["candidates"] += len(ev)
            events.extend(ev); sources.extend(so)
        pool = list(existing_events or [])
        dup = 0
        for e in events:
            d = find_duplicate(e, pool)
            if d:
                e["review_note"] = f"Possible duplicate of {d}."
                dup += 1
            pool.append(e)
        price = PRICES.get(self.client.model)
        report = {"run_id": self.run_id, "extractor": self.extractor_id, "model": self.client.model,
                  "documents": len(captures), "candidates": len(events), "duplicates": dup,
                  "input_tokens": in_tok, "output_tokens": out_tok,
                  "estimated_cost_usd": (in_tok * price[0] + out_tok * price[1]) / 1e6 if price else None,
                  "by_source": by_source, "failures": failures,
                  "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        return events, sources, report
