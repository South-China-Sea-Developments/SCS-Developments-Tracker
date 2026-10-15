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
        assert s["kind"] in ("rss", "html_list"), s["id"]
        assert s["status"] in ("active", "blocked_from_cloud", "needs_work"), s["id"]
        assert s["url"].startswith("http"), s["id"]
        assert set(s["claimants"]) <= set(schema.CLAIMANT_CODES), s["id"]
        assert s["cadence"] in ("daily", "weekly"), s["id"]
        assert s["language"], s["id"]
        if s["kind"] == "html_list":
            assert s["link_pattern"], s["id"]
        if s["status"] != "active":
            assert s["notes"], f"{s['id']}: an inactive source must say why"


# ---- parsers ----------------------------------------------------------------

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>A &amp; B</title><link>http://x/a</link><pubDate>Wed, 14 Oct 2026 17:41:00 GMT</pubDate><description>&lt;p&gt;Snippet&lt;/p&gt;</description><guid>g1</guid></item>
<item><title>C</title><link>http://x/c</link><pubDate>Mon, 05 Oct 2026 00:00:00 GMT</pubDate></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>E</title><link rel="alternate" href="http://y/e"/><id>u1</id><published>2026-10-01T10:00:00Z</published></entry></feed>"""


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


def test_parse_events_json_tolerates_fences_and_garbage():
    assert parse_events_json('```json\n{"events": [{"claimant": "CN"}]}\n```') == [{"claimant": "CN"}]
    assert parse_events_json("no json here") == []
    assert parse_events_json('{"events": "not a list"}') == []


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
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


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
    assert all(r["extractor"].endswith("@prompt-" + r["extractor"].split("@prompt-")[1]) and len(r["extractor"].split("@prompt-")[1]) == 12 for r in rows)
    assert all(r["suggestion_reasoning"] for r in rows)
    with open(fixture_run / "sources.csv", newline="", encoding="utf-8") as f:
        sources = list(csv.DictReader(f))
    assert [s["event_id"] for s in sources] == [r["event_id"] for r in rows]
    assert all(s["url"] and s["excerpt"] and len(s["excerpt"]) <= 400 and s["accessed_date"] for s in sources)
    report = json.loads((fixture_run / "run.json").read_text(encoding="utf-8"))
    assert report["captures"] == 7 and report["candidates"] == 4 and report["failures"] == []


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
    other_claimant = dict(same, claimant="PH")
    assert find_duplicate(other_claimant, existing) == ""
    far_away = dict(same, date_start="2026-11-20", date_end="2026-11-20")
    assert find_duplicate(far_away, existing) == ""
    unrelated = dict(same, location_name="Vanguard Bank", summary="A Chinese survey ship operated near Vanguard Bank escorted by coast guard ships.")
    assert find_duplicate(unrelated, existing) == ""


def test_extractor_drops_malformed_events():
    class Fake:
        model = "fake"
        def complete(self, system, user):
            return json.dumps({"events": [
                {"claimant": "XX", "date_start": "2026-01-01", "date_end": "2026-01-01", "summary": "bad claimant"},
                {"claimant": "VN", "date_start": "January 2026", "date_end": "", "summary": "bad date"},
                {"claimant": "VN", "date_start": "2026-01-01", "date_end": "2026-01-31", "date_precision": "weird",
                 "subregion": "42", "suggested_type": "nope", "suggested_domains": ["physical", "lunar"], "suggested_dyads": ["VC", "zz"],
                 "summary": "ok"}]}), 10, 5
    ex = Extractor(Fake(), run_id="t")
    events, sources, i, o = ex.extract_one({"guid": "g", "url": "u", "text": "x", "fetched_at": "2026-10-15T00:00:00+00:00"})
    assert len(events) == 1
    e = events[0]
    assert e["date_precision"] == "month" and e["subregion"] == "" and e["suggested_type"] == ""
    assert e["suggested_domains"] == "physical" and e["suggested_dyads"] == "VC"
    assert (i, o) == (10, 5)
