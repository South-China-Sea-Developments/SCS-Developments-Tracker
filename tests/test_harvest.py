"""Seam 2: the harvester on fixtures. No network: a local HTTP server stands in for the sources,
and the extractor replays recorded responses."""
import csv
import http.server
import json
import shutil
import threading
from pathlib import Path

import pytest

from pipeline import harvest, schema
from pipeline.extract import Extractor, RecordedClient, find_duplicate, parse_events_json
from pipeline.validate import validate
from tests.conftest import DATA_DIR, RAW_MAVD, RAW_XLSX, ROOT

FIX = ROOT / "tests/fixtures/harvest"
REQUIRED_SOURCES = {"amti", "scspi", "ph_pcg", "ph_dfa", "ph_bfar", "cn_mfa_press", "cn_ccg", "vn_mfa", "my_mmea", "id_kemlu",
                    "id_bakamla", "tw_mofa", "tw_cga", "scs_news"}


# ---- registry ---------------------------------------------------------------

def test_registry_is_complete_and_well_formed():
    sources = harvest.load_registry()
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids))
    assert REQUIRED_SOURCES <= set(ids)
    for s in sources:
        assert s["url"].startswith("http"), s["id"]
        assert set(s["claimants"]) <= set(schema.CLAIMANT_CODES), s["id"]
        assert s["language"], s["id"]
        if s["kind"] == "archive":   # ticket 12: where a coder looks for 1970-2015; never fetched
            assert s["status"] == "archival" and s["archive_kind"] in ("chronology", "yearbook", "government", "press_archive", "scholarly", "legal_deposit"), s["id"]
            start, end = s["coverage"]
            assert start <= 2015 and (end is None or end >= max(start, 1970)), (s["id"], "an archive must overlap 1970-2015")
            assert s["access"] in ("open", "free_registration", "paywalled", "library") and s["how_to_use"], s["id"]
            assert s["claimants"] and isinstance(s["reachable_from_cloud"], bool), s["id"]
            continue
        assert s["kind"] in ("rss", "html_list"), s["id"]
        assert s["status"] in ("active", "blocked_from_cloud", "needs_work"), s["id"]
        assert s["cadence"] in ("daily", "weekly"), s["id"]
        if s["kind"] == "html_list":
            assert s["link_pattern"], s["id"]
        if s["status"] != "active":
            assert s["notes"], f"{s['id']}: an inactive source must say why"


def test_archives_are_listed_but_never_fetched(tmp_path):
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"sources": [
        {"id": "arch", "name": "An archive", "kind": "archive", "archive_kind": "press_archive", "url": "https://example.org/arch", "language": "en",
         "claimants": ["MY"], "coverage": [1970, 1999], "access": "open", "how_to_use": "search", "status": "archival", "notes": ""}]}), encoding="utf-8")
    assert [s["id"] for s in harvest.archival_sources(reg)] == ["arch"]
    rc = harvest.main(["fetch", "--out", str(tmp_path / "cap"), "--sleep", "0", "--registry", str(reg)])
    assert rc == 0 and not list((tmp_path / "cap").rglob("arch*"))
    report = json.loads((tmp_path / "cap" / "fetch-report.json").read_text(encoding="utf-8"))
    assert report["sources"] == []
    assert harvest.main(["archives", "--registry", str(reg)]) == 0
    assert harvest.main(["probe", "--registry", str(reg)]) == 0   # an archive with an open end prints and never fails the probe


# ---- parsers ----------------------------------------------------------------

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>A &amp; B</title><link>http://x/a</link><pubDate>Wed, 14 Oct 2026 17:41:00 GMT</pubDate><description>&lt;p&gt;Snippet&lt;/p&gt;</description><guid>g1</guid></item>
<item><title>C</title><link>http://x/c</link><pubDate>Mon, 05 Oct 2026 00:00:00 GMT</pubDate></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>E</title><link rel="alternate" href="http://y/e"/><id>u1</id><published>2026-10-01T10:00:00Z</published></entry></feed>"""


RDF = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns="http://purl.org/rss/1.0/">
<channel rdf:about="https://example.org/"><title>T</title></channel>
<item rdf:about="https://example.org/a"><title>Coast guard statement</title><link>https://example.org/a</link><dc:date>2026-10-18T08:00:00+08:00</dc:date><description>&lt;p&gt;Text&lt;/p&gt;</description></item>
</rdf:RDF>"""


def test_parse_rss1_rdf():
    """Taipei Times publishes RSS 1.0: namespaced items with dc:date and no guid."""
    items = harvest.parse_rss(RDF)
    assert len(items) == 1 and items[0]["title"] == "Coast guard statement" and items[0]["link"] == "https://example.org/a"
    assert items[0]["guid"] == "https://example.org/a" and items[0]["summary"] == "Text"
    assert harvest.parse_date(items[0]["published"]) == "2026-10-18"


def test_parse_rss_and_atom():
    items = harvest.parse_rss(RSS)
    assert [i["title"] for i in items] == ["A & B", "C"]
    assert items[0]["summary"] == "Snippet" and items[0]["guid"] == "g1" and items[1]["guid"] == "http://x/c"
    assert harvest.parse_date(items[0]["published"]) == "2026-10-14"
    atom = harvest.parse_rss(ATOM)
    assert atom[0]["link"] == "http://y/e" and harvest.parse_date(atom[0]["published"]) == "2026-10-01"
    assert harvest.parse_date("garbage") == ""


def test_html_to_text_strips_chrome_and_keeps_title():
    body = b"<html><head><title>Hello &amp; welcome</title><style>p{}</style></head><body><nav>menu</nav><p>First.</p><script>x()</script><div>Second<br>line</div></body></html>"
    title, text = harvest.html_to_text(body, "text/html; charset=utf-8")
    assert title == "Hello & welcome"
    assert text == "First.\nSecond\nline"


def test_list_links_resolves_relative_and_dedupes():
    body = b'<a href="./202610/t1.html">x</a><a href="./202610/t1.html">y</a><a href="./202609/t2.html">z</a>'
    links = harvest.list_links(body, "https://h/eng/xw/", r'href="(\./\d{6}/t\d+\.html)"', 10)
    assert links == ["https://h/eng/xw/202610/t1.html", "https://h/eng/xw/202609/t2.html"]


def test_parse_events_json_tolerates_fences_and_prose_but_not_garbage():
    assert parse_events_json('```json\n{"events": [{"claimant": "CN"}]}\n```') == [{"claimant": "CN"}]
    assert parse_events_json('Here you go: {"events": []}\nNote: {see above}') == []
    assert parse_events_json("no json here") is None          # a failure, not "no events"
    assert parse_events_json('{"events": "not a list"}') is None
    assert parse_events_json('{"meta": {"events": [1]}, "events": [{"a": 1}, 2]}') == [{"a": 1}]


# ---- fetcher against a local server ------------------------------------------

@pytest.fixture(scope="module")
def local_site(tmp_path_factory):
    root = tmp_path_factory.mktemp("site")
    (root / "feed.xml").write_bytes(RSS.replace(b"http://x/a", b"/a.html").replace(b"http://x/c", b"/c.html"))
    (root / "a.html").write_text("<html><head><title>Article A</title></head><body><p>Body of A about Scarborough.</p></body></html>")
    (root / "c.html").write_text("<html><head><title>Article C</title></head><body><p>Body of C.</p></body></html>")
    (root / "list.html").write_text('<html><body><a href="./202610/t20261009_1.html">one</a><a href="./202610/t20261008_2.html">two</a></body></html>')
    (root / "202610").mkdir()
    (root / "202610/t20261009_1.html").write_text("<html><head><title>PC 9 Oct</title></head><body><p>Transcript one.</p></body></html>")
    (root / "202610/t20261008_2.html").write_text("<html><head><title>PC 8 Oct</title></head><body><p>Transcript two.</p></body></html>")
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(root), **k)
    (root / "doc.pdf").write_bytes(b"%PDF-1.4 binary")
    (root / "pdffeed.xml").write_bytes(b'<rss version="2.0"><channel><item><title>P</title><link>/doc.pdf</link><guid>pdf1</guid></item></channel></rss>')
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_fetch_rss_source_captures_articles(local_site, tmp_path):
    src = {"id": "t_rss", "name": "Test feed", "kind": "rss", "url": local_site + "/feed.xml", "language": "en",
           "claimants": ["PH"], "max_items": 10, "status": "active"}
    report = harvest.fetch_source(src, tmp_path, sleep=0)
    assert report["listed"] == 2 and report["captured"] == 2 and report["errors"] == []
    caps = sorted(tmp_path.glob("t_rss/*.json"))
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in caps]
    a = next(r for r in recs if r["title"] == "A & B")
    assert a["status"] == 200 and a["published"] == "2026-10-14" and "Scarborough" in a["text"]
    assert a["url"].endswith("/a.html") and a["fetched_at"] and a["capture_id"] == harvest.capture_id("g1")
    # a second fetch with --since newer than item C skips it; known guids are skipped too
    (tmp_path / "t_rss").rename(tmp_path / "gone")
    report = harvest.fetch_source(src, tmp_path, since="2026-10-10", known={"g1"}, sleep=0)
    assert report["listed"] == 1 and report["skipped"] == 1 and report["captured"] == 0


def test_fetch_html_list_source(local_site, tmp_path):
    src = {"id": "t_list", "name": "Test listing", "kind": "html_list", "url": local_site + "/list.html",
           "link_pattern": r'href="(\./\d{6}/t\d{8}_\d+\.html)"', "language": "en", "claimants": ["CN"], "max_items": 5, "status": "active"}
    report = harvest.fetch_source(src, tmp_path, sleep=0)
    assert report["captured"] == 2 and report["errors"] == []
    titles = sorted(json.loads(p.read_text(encoding="utf-8"))["title"] for p in tmp_path.glob("t_list/*.json"))
    assert titles == ["PC 8 Oct", "PC 9 Oct"]


def test_non_text_documents_are_not_captured_as_text(local_site, tmp_path):
    src = {"id": "t_pdf", "name": "PDF feed", "kind": "rss", "url": local_site + "/pdffeed.xml", "language": "en",
           "claimants": ["MY"], "max_items": 5, "status": "active"}
    report = harvest.fetch_source(src, tmp_path, sleep=0)
    rec = json.loads(next(tmp_path.glob("t_pdf/*.json")).read_text(encoding="utf-8"))
    assert rec["text"] == "" and rec["error"].startswith("not a text document") and report["document_errors"] == 1


def test_state_keeps_only_documents_that_yielded_text(local_site, tmp_path):
    """A failed document fetch is retried next run: its guid is not marked as seen."""
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"sources": [
        {"id": "ok", "name": "ok", "kind": "rss", "url": local_site + "/feed.xml", "language": "en", "claimants": ["PH"], "cadence": "daily", "max_items": 5, "status": "active"},
        {"id": "pdf", "name": "pdf", "kind": "rss", "url": local_site + "/pdffeed.xml", "language": "en", "claimants": ["MY"], "cadence": "daily", "max_items": 5, "status": "active"},
    ]}), encoding="utf-8")
    state = tmp_path / "state.json"
    rc = harvest.main(["fetch", "--out", str(tmp_path / "cap"), "--state", str(state), "--sleep", "0", "--registry", str(reg)])
    assert rc == 0
    seen = set(json.loads(state.read_text(encoding="utf-8"))["seen"])
    assert "g1" in seen and "pdf1" not in seen
    assert (tmp_path / "cap" / "fetch-report.json").exists()


def test_fetch_reports_http_errors_without_raising(local_site, tmp_path):
    src = {"id": "t_404", "name": "Missing", "kind": "rss", "url": local_site + "/nope.xml", "language": "en",
           "claimants": ["CN"], "max_items": 5, "status": "active"}
    report = harvest.fetch_source(src, tmp_path, sleep=0)
    assert report["captured"] == 0 and report["errors"] and "HTTP 404" in report["errors"][0]


# ---- extractor on the frozen fixture -------------------------------------------

@pytest.fixture(scope="module")
def fixture_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("run")
    rc = harvest.main(["extract", "--captures", str(FIX / "captures"), "--out", str(out),
                       "--recordings", str(FIX / "recordings"), "--run-id", "fixture"])
    assert rc == 0
    return out


def test_fixture_yields_the_expected_candidates(fixture_run):
    with open(fixture_run / "candidates.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    expected = json.loads((FIX / "expected_candidates.json").read_text(encoding="utf-8"))
    assert [{k: r[k] for k in expected[0]} for r in rows] == expected
    assert all(r["status"] == "candidate" and r["move_id"] == "" and r["harvest_run_id"] == "fixture" for r in rows)
    assert all(r["extractor"] == "hand-authored-fixture@prompt-" + r["extractor"].rsplit("-", 1)[1] and len(r["extractor"].rsplit("-", 1)[1]) == 12 for r in rows)
    # the duplicate path is exercised: the two same-day China events are flagged for the reviewer, not dropped
    flagged = [r for r in rows if r["review_note"].startswith("Possible duplicate of ")]
    assert len(flagged) == 1 and flagged[0]["location_name"].startswith("Thitu")
    assert {r["claimant"] for r in rows} == {"CN", "VN"}
    assert all(r["suggestion_reasoning"] for r in rows)
    with open(fixture_run / "sources.csv", newline="", encoding="utf-8") as f:
        sources = list(csv.DictReader(f))
    assert [s["event_id"] for s in sources] == [r["event_id"] for r in rows]
    assert all(s["url"] and s["excerpt"] and len(s["excerpt"]) <= 400 and s["accessed_date"] for s in sources)
    report = json.loads((fixture_run / "run.json").read_text(encoding="utf-8"))
    assert report["documents"] == 7 and report["candidates"] == 5 and report["failures"] == []
    assert report["by_source"]["cn_mfa_press"] == {"documents": 2, "candidates": 3, "failures": 0, "irrelevant": 0}
    assert report["estimated_cost_usd"] is None   # unknown model -> unknown, never a silent zero


def test_candidates_fit_the_canonical_schema(fixture_run, tmp_path):
    """Candidates appended to the real data pass the validator (that is what the review PR will do)."""
    d = tmp_path / "data"
    shutil.copytree(DATA_DIR, d, ignore=shutil.ignore_patterns("raw", "reference", "README.md"))
    for name, src in (("events", "candidates"), ("sources", "sources")):
        with open(fixture_run / f"{src}.csv", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        with open(d / f"{name}.csv", "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=schema.TABLES[name], lineterminator="\n")
            w.writerows(rows)
    assert validate(d, RAW_XLSX, RAW_MAVD) == []


def test_recorded_client_refuses_unknown_prompts():
    client = RecordedClient(FIX / "recordings")
    with pytest.raises(FileNotFoundError):
        client.complete("system", "a prompt nobody recorded")


def test_duplicate_detection():
    existing = [{"event_id": "ev-old", "claimant": "CN", "date_start": "2026-10-08", "date_end": "2026-10-08",
                 "location_name": "Second Thomas Shoal", "summary": "China Coast Guard fired water cannon at a Philippine Coast Guard vessel during a medical evacuation at Second Thomas Shoal."}]
    same = {"event_id": "ev-new", "claimant": "CN", "date_start": "2026-10-09", "date_end": "2026-10-09",
            "location_name": "Second Thomas Shoal", "summary": "CCG used water cannon against a PCG vessel on a medical evacuation mission at Second Thomas Shoal."}
    assert find_duplicate(same, existing) == "ev-old"
    parenthetical = dict(same, location_name="Second Thomas Shoal (Ren'ai Jiao)",
                         summary="CCG water cannon against a PCG resupply at Second Thomas Shoal (Ren'ai Jiao) during a rotation.")
    assert find_duplicate(parenthetical, existing) == "ev-old"   # location match carries a weaker summary match
    other_claimant = dict(same, claimant="PH")
    assert find_duplicate(other_claimant, existing) == ""
    far_away = dict(same, date_start="2026-11-20", date_end="2026-11-20")
    assert find_duplicate(far_away, existing) == ""
    unrelated = dict(same, location_name="Vanguard Bank", summary="A Chinese survey ship operated near Vanguard Bank escorted by coast guard ships.")
    assert find_duplicate(unrelated, existing) == ""


class _Fake:
    model = "fake-model"
    def __init__(self, text, stop="end_turn"):
        self.text, self.stop = text, stop
    def complete(self, system, user):
        return self.text, 10, 5, self.stop


def test_extractor_drops_malformed_events_and_sanitises_fields():
    fake = _Fake(json.dumps({"events": [
        {"claimant": "XX", "date_start": "2026-01-01", "date_end": "2026-01-01", "summary": "bad claimant"},
        {"claimant": "VN", "date_start": "January 2026", "date_end": "", "summary": "bad date"},
        {"claimant": "VN", "date_start": "2026-13-45", "date_end": "2026-13-45", "summary": "impossible date"},
        {"claimant": "VN", "date_start": "2026-02-10", "date_end": "2026-02-01", "summary": "end before start"},
        {"claimant": "VN", "date_start": "2026-01-01", "date_end": "2026-01-31", "date_precision": "weird",
         "subregion": "42", "suggested_type": "nope", "suggested_domains": ["physical", "lunar"], "suggested_dyads": ["VC", "zz"],
         "lat": {"x": 1}, "lon": "999", "summary": "=HYPERLINK(evil)", "excerpt": "not in the document", "confidence": "certain"}]}))
    ex = Extractor(fake, run_id="t")
    events, sources, i, o = ex.extract_one({"guid": "g", "url": "u", "text": "the real text", "fetched_at": "2026-10-15T00:00:00+00:00"})
    assert len(events) == 1
    e = events[0]
    assert e["date_precision"] == "month" and e["subregion"] == "" and e["suggested_type"] == ""
    assert e["suggested_domains"] == "physical" and e["suggested_dyads"] == "VC"
    assert e["lat"] == "" and e["lon"] == ""
    assert e["summary"].startswith("'=")                       # never a live formula in a spreadsheet
    assert e["actors"] == "" and e["location_name"] == ""      # empty stays empty
    assert "Excerpt not found verbatim" in e["review_note"]
    assert e["suggestion_reasoning"].endswith("[confidence: unstated]")
    assert e["extractor"].startswith("fake-model@prompt-")
    assert (i, o) == (10, 5)


def test_truncated_or_non_json_responses_are_failures_not_quiet_weeks():
    cap = {"capture_id": "c1", "source_id": "s", "guid": "g", "url": "u", "text": "x", "fetched_at": "2026-10-15T00:00:00+00:00"}
    ex = Extractor(_Fake('{"events": [{"claimant": "CN", "date_start": "2026-01-01', stop="max_tokens"), run_id="t")
    events, sources, report = ex.extract_all([cap])
    assert events == [] and len(report["failures"]) == 1 and "truncated" in report["failures"][0]["error"]
    ex = Extractor(_Fake("Sorry, I cannot help with that."), run_id="t")
    events, sources, report = ex.extract_all([cap])
    assert events == [] and len(report["failures"]) == 1 and "not the requested JSON" in report["failures"][0]["error"]
    assert report["by_source"]["s"] == {"documents": 1, "candidates": 0, "failures": 1, "irrelevant": 0}


def test_excerpt_check_ignores_quote_style_and_whitespace():
    from pipeline.extract import excerpt_in_text
    assert excerpt_in_text("China’s permission,  intruded", "without China's permission, intruded the")
    assert not excerpt_in_text("something else entirely", "without China's permission")
    assert not excerpt_in_text("", "anything")


def test_import_hand_compiled_candidates(tmp_path, monkeypatch):
    """Hand-compiled events enter the queue through the extractor's own normalisation: same ids,
    same cleaning, same duplicate flagging, the compiler named as the extractor."""
    monkeypatch.setattr(harvest, "ROOT", tmp_path)   # duplicates are checked against ROOT/data/events.csv: none here
    items = [
        {"date_start": "2016-06-17", "date_end": "2016-06-17", "date_precision": "day", "claimant": "ID", "location_name": "Natuna waters",
         "subregion": "10", "summary": "KRI Imam Bonjol fires on Chinese boats.", "actors": "TNI AL",
         "sources": [{"url": "https://example.org/a", "title": "A", "publisher": "Reuters", "pub_date": "2016-06-18", "excerpt": "fired warning shots"},
                     {"url": "https://example.org/b", "title": "B", "publisher": "AMTI", "pub_date": "", "excerpt": "second account"}],
         "suggested_type": "coercive", "suggested_domains": ["physical"], "suggested_issues": ["fisheries"], "suggested_dyads": ["IC"],
         "reasoning": "Warning shots and detention.", "confidence": "high"},
        {"date_start": "not a date", "claimant": "ID", "sources": [{"url": "https://example.org/c"}]},   # dropped: invalid date
        {"date_start": "2016-06-17", "claimant": "ID", "summary": "no source"},                          # dropped: no source
    ]
    f = tmp_path / "events.json"
    f.write_text(json.dumps(items), encoding="utf-8")
    out = tmp_path / "run"
    assert harvest.main(["import", str(f), "--run-id", "manual-test", "--out", str(out), "--extractor", "researcher", "--no-fetch"]) == 0
    cands = list(csv.DictReader(open(out / "candidates.csv", newline="", encoding="utf-8")))
    srcs = list(csv.DictReader(open(out / "sources.csv", newline="", encoding="utf-8")))
    assert len(cands) == 1 and len(srcs) == 2
    c = cands[0]
    assert c["event_id"].startswith("ev-") and c["status"] == "candidate" and c["harvest_run_id"] == "manual-test"
    assert c["extractor"] == "manual:researcher" and c["suggested_type"] == "coercive" and c["suggested_dyads"] == "IC"
    assert c["review_note"] == "Excerpt not checked against the source (imported without fetching)."
    assert [s["source_id"] for s in srcs] == [c["event_id"] + "-S01", c["event_id"] + "-S02"] and srcs[1]["publisher"] == "AMTI"
    assert srcs[0]["accessed_date"] == "" and srcs[0]["language"] == ""
    report = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert report["candidates"] == 1 and len(report["failures"]) == 2 and report["estimated_cost_usd"] is None


def test_import_checks_excerpts_and_flags_duplicates(tmp_path, monkeypatch):
    """With fetching: an HTML page is compared, a PDF or an unreachable page is said to be unchecked;
    a candidate that repeats the dataset or an earlier candidate is flagged once, like extract_all."""
    pages = {"https://example.org/html": (200, "text/html; charset=utf-8", b"<html><body><p>The corvette fired warning shots at the boats.</p></body></html>"),
             "https://example.org/pdf": (200, "application/pdf", b"%PDF-1.4 binary"),
             "https://example.org/gone": (404, "text/html", b"")}
    monkeypatch.setattr(harvest, "http_get", lambda url, timeout=0: pages[url] + (url,))
    monkeypatch.setattr(harvest.time, "sleep", lambda s: None)
    monkeypatch.setattr(harvest, "ROOT", tmp_path)   # not against the live dataset, which may hold this very event
    base = {"date_start": "2016-06-17", "date_end": "2016-06-17", "date_precision": "day", "claimant": "ID", "location_name": "Natuna waters",
            "subregion": "10", "actors": "", "suggested_type": "coercive", "suggested_domains": ["physical"], "suggested_issues": ["fisheries"],
            "suggested_dyads": ["IC"], "reasoning": "r", "confidence": "high"}
    items = [dict(base, summary="KRI Imam Bonjol fired warning shots at Chinese fishing boats off Natuna.",
                  sources=[{"url": "https://example.org/html", "title": "A", "publisher": "P", "pub_date": "Mon, 20 Jun 2016 10:00:00 +0000", "excerpt": "fired warning shots at the boats"}]),
             dict(base, summary="KRI Imam Bonjol fired warning shots at Chinese fishing boats off Natuna, seizing one.",   # repeats the first
                  sources=[{"url": "https://example.org/pdf", "title": "B", "publisher": "Q", "pub_date": "", "excerpt": "anything"}]),
             dict(base, date_start="2016-03-19", date_end="2016-03-19", summary="KP Hiu 11 arrested the trawler Kway Fey.",
                  sources=[{"url": "https://example.org/gone", "title": "C", "publisher": "R", "pub_date": "", "excerpt": "arrested"}])]
    f = tmp_path / "events.json"
    f.write_text(json.dumps(items), encoding="utf-8")
    out = tmp_path / "run"
    assert harvest.main(["import", str(f), "--run-id", "t", "--out", str(out), "--extractor", "x"]) == 0
    cands = list(csv.DictReader(open(out / "candidates.csv", newline="", encoding="utf-8")))
    srcs = list(csv.DictReader(open(out / "sources.csv", newline="", encoding="utf-8")))
    assert cands[0]["review_note"] == ""                                              # excerpt found on the page
    assert cands[1]["review_note"] == f"Source is application/pdf; excerpt not checked. Possible duplicate of {cands[0]['event_id']}."
    assert cands[2]["review_note"] == "Source page could not be fetched (HTTP 404); excerpt not checked."
    assert srcs[0]["pub_date"] == "2016-06-20" and srcs[0]["accessed_date"] and srcs[0]["language"] == ""
    report = json.loads((out / "run.json").read_text(encoding="utf-8"))
    assert report["duplicates"] == 1 and report["extractor"] == "manual:x"
