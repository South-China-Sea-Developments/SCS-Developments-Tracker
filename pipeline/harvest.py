"""Harvest: fetch the registered sources, save raw captures, and (separately) extract candidate events.

Stages, each a command:
  probe    check every registered source is reachable and report
  fetch    fetch new items from active sources into a capture folder (one JSON file per document);
           --since filters feed items by publication date (listing pages carry no dates); --state keeps
           the guids of documents already captured with text so they are not fetched again
  extract  turn a capture folder into candidate events + sources in the canonical schema
  run      fetch then extract

A capture folder is a plain directory and is also what the tests use as a fixture. The language
model is reached through a small client interface with a recorded-response layer, so tests run
offline and a live run can be re-played.

Usage:
  python -m pipeline.harvest probe
  python -m pipeline.harvest fetch   --out harvest/captures/<run_id> [--since YYYY-MM-DD] [--only id,id]
  python -m pipeline.harvest extract --captures DIR --out harvest/runs/<run_id> [--recordings DIR] [--record]
  python -m pipeline.harvest run     --run-id <id>
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from pipeline import schema
from pipeline.extract import Extractor, LLMClient, RecordedClient, RecordingClient, AnthropicClient

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "pipeline" / "sources.json"
USER_AGENT = "Mozilla/5.0 (compatible; SCSTrackerBot/0.1; +https://github.com/South-China-Sea-Developments/SCS-Developments-Tracker)"
MAX_TEXT = 20000      # characters of plain text kept per capture (press conferences are long)
MAX_BODY = 3_000_000  # bytes read per document; anything larger is cut (text pages are far smaller)
TIMEOUT = 30          # per socket operation
TEXT_TYPES = ("html", "xml", "text/plain", "json")


# ---------------------------------------------------------------------------
# registry

def load_registry(path: Path = REGISTRY) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["sources"]


# ---------------------------------------------------------------------------
# fetching

def _ssl_context() -> ssl.SSLContext:
    """Default verification, minus Python 3.13's extra X.509 strictness: some government certificate
    chains (Taiwan's GCA) lack a Subject Key Identifier and are rejected only under the strict flag."""
    ctx = ssl.create_default_context()
    ctx.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)
    return ctx


SSL_CONTEXT = _ssl_context()


def http_get(url: str, timeout: int = TIMEOUT) -> tuple[int, str, bytes, str]:
    """(status, content_type, body, final_url). Never raises for HTTP errors; raises for network errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read(MAX_BODY), resp.geturl()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read(MAX_BODY) if e.fp else b"", url


class _TextExtractor(HTMLParser):
    """Plain text from HTML: drops script/style/nav/header/footer, keeps block breaks, reads <title>."""
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "svg", "iframe"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in raw.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(ln for ln in lines if ln)).strip()


def html_to_text(body: bytes, content_type: str = "") -> tuple[str, str]:
    enc = "utf-8"
    m = re.search(r"charset=([\w-]+)", content_type or "")
    if m:
        enc = m.group(1)
    else:
        m2 = re.search(rb'charset=["\']?([\w-]+)', body[:4000])
        if m2:
            enc = m2.group(1).decode("ascii", "ignore")
    try:
        text = body.decode(enc, errors="replace")
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    p = _TextExtractor()
    try:
        p.feed(text)
    except Exception:  # malformed markup: keep what we got
        pass
    return re.sub(r"\s+", " ", p.title).strip(), p.text()


def parse_rss(body: bytes) -> list[dict]:
    """Items of an RSS 2.0 or Atom feed: {title, link, published, summary, guid}."""
    root = ET.fromstring(body)
    items = []
    ns_atom = "{http://www.w3.org/2005/Atom}"
    for it in root.iter("item"):
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "published": (it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip(),
            "summary": re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or "")).strip(),
            "guid": (it.findtext("guid") or it.findtext("link") or "").strip(),
        })
    for it in root.iter(ns_atom + "entry"):
        link = ""
        for ln in it.findall(ns_atom + "link"):
            if ln.get("rel", "alternate") == "alternate":
                link = ln.get("href", "")
        items.append({
            "title": (it.findtext(ns_atom + "title") or "").strip(), "link": link,
            "published": (it.findtext(ns_atom + "published") or it.findtext(ns_atom + "updated") or "").strip(),
            "summary": re.sub(r"<[^>]+>", " ", html.unescape(it.findtext(ns_atom + "summary") or "")).strip(),
            "guid": (it.findtext(ns_atom + "id") or link).strip(),
        })
    return items


def parse_date(s: str) -> str:
    """RFC 2822 or ISO date -> YYYY-MM-DD, or ''."""
    if not s:
        return ""
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return m.group(0) if m else ""


def list_links(body: bytes, base_url: str, pattern: str, limit: int) -> list[str]:
    text = body.decode("utf-8", errors="replace")
    seen, out = set(), []
    for m in re.finditer(pattern, text):
        href = html.unescape(m.group(1))
        url = urllib.parse.urljoin(base_url, href)
        if url not in seen:
            seen.add(url)
            out.append(url)
        if len(out) >= limit:
            break
    return out


def capture_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def fetch_source(src: dict, out_dir: Path, since: str = "", known: set[str] | None = None, sleep: float = 0.5) -> dict:
    """Fetch one source's new documents into out_dir/<source_id>/. Returns a small report."""
    known = known or set()
    report = {"source": src["id"], "listed": 0, "captured": 0, "skipped": 0, "document_errors": 0, "errors": []}
    sdir = out_dir / src["id"]
    sdir.mkdir(parents=True, exist_ok=True)
    try:
        status, ctype, body, final = http_get(src["url"])
    except Exception as e:  # network-level failure
        report["errors"].append(f"{src['url']}: {e}")
        return report
    if status != 200:
        report["errors"].append(f"{src['url']}: HTTP {status}")
        return report

    docs: list[dict] = []
    if src["kind"] == "rss":   # --since applies to feed items only; listing pages carry no dates
        try:
            items = parse_rss(body)
        except ET.ParseError as e:
            report["errors"].append(f"{src['url']}: feed parse error {e}")
            return report
        for it in items[: src.get("max_items", 20)]:
            pub = parse_date(it["published"])
            if since and pub and pub < since:
                continue
            link = urllib.parse.urljoin(final, it["link"])     # feeds may carry relative links
            docs.append({"url": link, "guid": it["guid"] or link, "title": it["title"],
                         "published": pub, "feed_summary": it["summary"]})
    else:
        for url in list_links(body, final, src["link_pattern"], src.get("max_items", 20)):
            docs.append({"url": url, "guid": url, "title": "", "published": "", "feed_summary": ""})
    report["listed"] = len(docs)

    for d in docs:
        if d["guid"] in known:
            report["skipped"] += 1
            continue
        cid = capture_id(d["guid"])
        path = sdir / f"{cid}.json"
        if path.exists():
            report["skipped"] += 1
            continue
        rec = {"capture_id": cid, "source_id": src["id"], "source_name": src["name"], "language": src["language"],
               "claimants": src["claimants"], "url": d["url"], "guid": d["guid"], "title": d["title"],
               "published": d["published"], "feed_summary": d["feed_summary"],
               "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "status": None, "final_url": "", "content_type": "", "text": "", "error": ""}
        try:
            st, ct, b, fin = http_get(d["url"])
            rec["status"], rec["content_type"], rec["final_url"] = st, ct, fin
            if st != 200:
                rec["error"] = f"HTTP {st}"
            elif not ct or any(k in ct for k in TEXT_TYPES):
                title, text = html_to_text(b, ct)
                rec["title"] = rec["title"] or title
                rec["text"] = text[:MAX_TEXT]
            else:
                rec["error"] = f"not a text document ({ct.split(';')[0]})"   # PDFs, images: not sent to the model
        except Exception as e:
            rec["error"] = str(e)[:200]
        if not rec["text"] and d["feed_summary"]:
            rec["text"] = d["feed_summary"]            # the aggregator's snippet is better than nothing
        if rec["error"]:
            report["document_errors"] += 1
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        report["captured"] += 1
        time.sleep(sleep)
    return report


def cmd_fetch(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None
    known = set()
    state_path = Path(args.state) if args.state else None
    if state_path and state_path.exists():
        known = set(json.loads(state_path.read_text(encoding="utf-8")).get("seen", []))
    reports = []
    for src in load_registry(args.registry):
        if src["status"] != "active" or (only and src["id"] not in only):
            continue
        r = fetch_source(src, out, since=args.since, known=known, sleep=args.sleep)
        reports.append(r)
        print(f"{src['id']:<12} listed {r['listed']:>3} captured {r['captured']:>3} skipped {r['skipped']:>3} "
              f"document errors {r['document_errors']:>2}" + (f"  errors: {'; '.join(r['errors'])[:160]}" if r["errors"] else ""))
    (out / "fetch-report.json").write_text(json.dumps({"fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                                       "since": args.since, "sources": reports}, indent=1), encoding="utf-8")
    if state_path:
        # only documents that yielded text count as seen; failed fetches are retried next run
        seen = set(known)
        for p in out.rglob("*.json"):
            if p.name == "fetch-report.json":
                continue
            rec = json.loads(p.read_text(encoding="utf-8"))
            if rec.get("text"):
                seen.add(rec["guid"])
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"seen": sorted(seen)}, indent=0), encoding="utf-8")
    failed = [r["source"] for r in reports if r["errors"]]
    if reports and len(failed) == len(reports):
        print("every active source failed", file=sys.stderr)
        return 1
    return 0


def cmd_probe(args) -> int:
    ok = True
    for src in load_registry(args.registry):
        try:
            st, ct, body, final = http_get(src["url"], timeout=20)
            n = ""
            if st == 200:
                if src["kind"] == "rss":
                    try:
                        n = f"{len(parse_rss(body))} items"
                    except ET.ParseError:
                        n = "feed parse error"
                else:
                    n = f"{len(list_links(body, final, src['link_pattern'], 50))} links"
            print(f"{src['id']:<12} {src['status']:<18} HTTP {st:<4} {n}")
            if src["status"] == "active" and (st != 200 or n.endswith("error") or n.startswith("0 ")):
                ok = False
        except Exception as e:
            print(f"{src['id']:<12} {src['status']:<18} ERROR {str(e)[:80]}")
            if src["status"] == "active":
                ok = False
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# extraction

def load_captures(captures_dir: Path) -> list[dict]:
    out = []
    for p in sorted(Path(captures_dir).rglob("*.json")):
        if p.name == "fetch-report.json":
            continue
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("text"):
            out.append(rec)
    return out


def make_client(args) -> LLMClient:
    recordings = Path(args.recordings) if args.recordings else None
    if args.record:
        return RecordingClient(AnthropicClient(model=args.model), recordings or ROOT / "harvest" / "recordings")
    if recordings:
        return RecordedClient(recordings)
    return AnthropicClient(model=args.model)


def cmd_extract(args) -> int:
    captures = load_captures(Path(args.captures))
    client = make_client(args)
    ex = Extractor(client, run_id=args.run_id or Path(args.out).name)
    existing = []
    events_csv = ROOT / "data" / "events.csv"
    if events_csv.exists():
        with open(events_csv, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    events, sources, report = ex.extract_all(captures, existing_events=existing)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("candidates", events), ("sources", sources)):
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            cols = schema.TABLES["events" if name == "candidates" else "sources"]
            w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in cols})
    (out / "run.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    cost = f"${report['estimated_cost_usd']:.2f}" if report["estimated_cost_usd"] is not None else "unknown"
    print(f"documents {report['documents']}, candidates {report['candidates']}, possible duplicates {report['duplicates']}, "
          f"tokens in/out {report['input_tokens']}/{report['output_tokens']}, estimated cost {cost}, "
          f"failures {len(report['failures'])} -> {out}/")
    for sid, s in report["by_source"].items():
        print(f"  {sid:<12} documents {s['documents']:>3} candidates {s['candidates']:>3} failures {s['failures']:>2}")
    return 1 if report["failures"] and not report["candidates"] else 0


def cmd_run(args) -> int:
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M")
    ns = argparse.Namespace(out=str(ROOT / "harvest" / "captures" / run_id), since=args.since, only=args.only,
                            registry=args.registry, state=str(ROOT / "harvest" / "state.json"), sleep=args.sleep)
    cmd_fetch(ns)
    ns2 = argparse.Namespace(captures=ns.out, out=str(ROOT / "harvest" / "runs" / run_id), recordings=args.recordings,
                             record=args.record, model=args.model, run_id=run_id)
    return cmd_extract(ns2)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    common = {"registry": dict(default=REGISTRY, type=Path)}
    sp = sub.add_parser("probe"); sp.add_argument("--registry", **common["registry"]); sp.set_defaults(fn=cmd_probe)
    sf = sub.add_parser("fetch"); sf.add_argument("--out", required=True); sf.add_argument("--since", default="")
    sf.add_argument("--only", default=""); sf.add_argument("--state", default=""); sf.add_argument("--sleep", type=float, default=0.5)
    sf.add_argument("--registry", **common["registry"]); sf.set_defaults(fn=cmd_fetch)
    se = sub.add_parser("extract"); se.add_argument("--captures", required=True); se.add_argument("--out", required=True)
    se.add_argument("--recordings", default=""); se.add_argument("--record", action="store_true")
    se.add_argument("--model", default=Extractor.DEFAULT_MODEL); se.add_argument("--run-id", default=""); se.set_defaults(fn=cmd_extract)
    sr = sub.add_parser("run"); sr.add_argument("--run-id", default=""); sr.add_argument("--since", default="")
    sr.add_argument("--only", default=""); sr.add_argument("--sleep", type=float, default=0.5); sr.add_argument("--recordings", default="")
    sr.add_argument("--record", action="store_true"); sr.add_argument("--model", default=Extractor.DEFAULT_MODEL)
    sr.add_argument("--registry", **common["registry"]); sr.set_defaults(fn=cmd_run)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
