"""Seam 3: the site build. Aggregates equal the validator's; pages render without errors; bundle is portable."""
import json
import re
from html import escape as html_escape
from pathlib import Path

import pytest

from pipeline.validate import aggregates
from tests.conftest import DATA_DIR as LIVE_DATA_DIR

DATA_DIR = LIVE_DATA_DIR   # rebound to the MATS-only copy below: these tests check the site against Chubb's known counts


@pytest.fixture(scope="module", autouse=True)
def _mats_only(mats_data):
    global DATA_DIR
    DATA_DIR = mats_data
from web.build import build, read_csv


EMPTY_TILEJSON = json.dumps({"tilejson": "3.0.0", "tiles": ["https://tiles.openfreemap.org/stub/{z}/{x}/{y}.pbf"], "minzoom": 0, "maxzoom": 14, "vector_layers": []})
HEADLESS_NOISE = re.compile(r"WebGL|swiftshader|GL Driver|GPU stall", re.I)


def _stale_tile(request) -> bool:
    """A stub tile the map cancelled because the view moved on: MapLibre aborts the tiles of a zoom it
    has left, which is normal and not a failure of the page."""
    return "/stub/" in request.url and "abort" in (request.failure or "").lower()


@pytest.fixture(scope="module")
def dist(tmp_path_factory, mats_data):
    out = tmp_path_factory.mktemp("dist")
    build(mats_data, out, build_date="2026-01-01")
    return out


def test_aggregates_match_validator(dist):
    built = json.loads((dist / "data/aggregates.json").read_text(encoding="utf-8"))
    independent = aggregates(read_csv(DATA_DIR / "moves.csv"))
    for key in ("years", "types", "domains", "issues", "subregions", "claimants", "n_moves", "n_pending", "by_claimant"):
        assert built[key] == independent[key], key
    # the inline copy the page uses is the same data
    inline = re.search(r'<script id="agg" type="application/json">(.*?)</script>', (dist / "trends.html").read_text(encoding="utf-8"), re.S)
    assert json.loads(inline.group(1))["by_claimant"] == independent["by_claimant"]


def test_known_counts_appear_in_aggregates(dist):
    a = json.loads((dist / "data/aggregates.json").read_text(encoding="utf-8"))
    assert a["by_claimant"]["CN"]["totals"]["total"] == 144
    assert a["by_claimant"]["VN"]["totals"]["total"] == 111
    assert a["by_claimant"]["PH"]["totals"]["total"] == 102
    assert a["by_claimant"]["MY"]["totals"]["total"] == 0
    assert a["by_claimant"]["CN"]["years"]["1974"]["force"] == 1  # Paracels, January 1974
    assert a["n_pending"] == 1


def test_bundle_is_self_contained_and_relative(dist):
    for page in ("index.html", "methodology.html", "cases.html", "cases/VN197301.html", "cases/CN201105.html", "downloads.html", "map.html"):
        html = (dist / page).read_text(encoding="utf-8")
        # every src/href that is not an external link is relative and resolves from the page's own folder
        for attr, target in re.findall(r'(src|href)="([^"]+)"', html):
            assert not target.startswith("/"), (page, target)
            if not target.startswith(("http://", "https://", "#", "mailto:")):
                assert ((dist / page).parent / target.split("#")[0]).resolve().exists(), (page, target)
    css = (dist / "assets/style.css").read_text(encoding="utf-8")
    for url in re.findall(r'url\("([^"]+)"\)', css):
        assert (dist / "assets" / url).exists(), url
    assert not re.search(r"https?://", css)  # no runtime dependency on any host from the stylesheet
    assert not re.search(r"https?://", (dist / "assets/charts.js").read_text(encoding="utf-8").replace("http://www.w3.org/2000/svg", ""))


def _open(browser, dist, page_name, viewport=(1280, 900), curtain=False):
    """Any page, offline: the basemap host is answered by the same stubs as on the map page, since
    the home page carries the map too."""
    ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
    if not curtain:   # the home page's opening curtain shows once per reader: these tests are returning readers
        ctx.add_init_script("try { localStorage.setItem('scs-curtain-seen', '1'); } catch (e) {}")
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(("console", m.type, m.text)) if m.type in ("error", "warning") and not HEADLESS_NOISE.search(m.text) else None)
    page.on("pageerror", lambda e: problems.append(("pageerror", str(e))))
    page.on("requestfailed", lambda r: None if _stale_tile(r) else problems.append(("requestfailed", r.url)))
    page.route("https://tiles.openfreemap.org/**", _tile_stub([]))
    page.goto((dist / page_name).resolve().as_uri())
    page.wait_for_timeout(300 if page_name not in ("index.html", "map.html") else 1200)
    page.on("close", lambda _: ctx.close())
    return page, problems


def _tile_stub(tiles):
    def stub(route):
        url = route.request.url
        tiles.append(url)
        if url.rstrip("/").endswith("/planet"):
            route.fulfill(status=200, content_type="application/json", body=EMPTY_TILEJSON)
        else:   # tiles, fonts and sprites: no content (a 404 would be a console error of the browser's own)
            route.fulfill(status=204, body=b"")
    return stub


@pytest.mark.parametrize("page_name", ["index.html", "map.html", "trends.html", "methodology.html", "cases.html", "downloads.html"])
@pytest.mark.parametrize("viewport", [(1280, 900), (1024, 768), (390, 800)])
def test_pages_render_without_errors(browser, dist, page_name, viewport):
    page, problems = _open(browser, dist, page_name, viewport)
    assert problems == []
    assert page.title()
    assert not page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "horizontal page scroll"
    if page_name == "trends.html":
        # the main chart fits the viewport at phone width (no internal scroll hiding recent years)
        assert page.locator('[data-chart="all-claimants"].is-scrollable').count() == 0
    page.close()


def test_tracker_is_the_home_page(browser, dist):
    """Ticket 17: the home page is the tracker — the sidebar lists the events in view newest first (all of
    them, by default) with a link to each move, the search box narrows them, and the map takes at least
    half of a desktop viewport once the page is scrolled to it."""
    page, problems = _open(browser, dist, "map.html")
    assert problems == []
    moves = {m["move_id"]: m for m in read_csv(DATA_DIR / "moves.csv")}
    events = [e for e in read_csv(DATA_DIR / "events.csv") if e["status"] == "accepted" and moves[e["move_id"]]["status"] == "accepted"]
    # newest first; ties on the date break on the event id, as the page does
    events.sort(key=lambda e: (e["date_start"] or f"{moves[e['move_id']]['year']}-01-01", e["event_id"]))
    events.sort(key=lambda e: e["date_start"] or f"{moves[e['move_id']]['year']}-01-01", reverse=True)
    rows = page.locator("#event-list .event-row")
    assert rows.count() == min(60, len(events)) and page.evaluate("document.getElementById('map-count').textContent").startswith(f"{len(events)} events")
    assert [r.get_attribute("data-event") for r in rows.element_handles()[:10]] == [e["event_id"] for e in events[:10]]
    assert rows.first.locator("a.case-id").get_attribute("href") == f"cases/{events[0]['move_id']}.html"
    # a seed event shows its move's description, not the mechanical seed summary
    assert "seed event" not in rows.first.inner_text().lower()
    # the list comes a page at a time; "show more" extends it
    if len(events) > 60:
        page.click("#event-list .list-more .more")
        page.wait_for_timeout(200)
        assert page.locator("#event-list .event-row").count() == min(120, len(events))
    # the map fills the viewport beside the sidebar
    assert page.locator("#map canvas.maplibregl-canvas").count() == 1 and page.locator(".sr-label").count() == 10
    page.evaluate("document.querySelector('.tracker').scrollIntoView()")
    page.wait_for_timeout(200)
    visible = page.evaluate("(() => { const r = document.getElementById('map').getBoundingClientRect(); return Math.min(r.bottom, innerHeight) - Math.max(r.top, 0); })()")
    assert visible >= 0.5 * 900, f"{visible}px of map visible"
    # search narrows the list and the count
    page.fill("#search", "drill")   # a word in summaries, not in a sub-region name or a move id
    page.wait_for_timeout(300)
    # the search looks through the text the row shows (the move's description for a seed event, else the summary) and the place
    def shown_text(e):   # what the row shows: the move's description (minus its leading date) for a seed event, else the summary; 400 characters at most
        text = re.sub(r"^\d{4}[^:]{0,24}:\s*", "", moves[e["move_id"]]["description"]) if e["harvest_run_id"] == "seed-mats-1.02" else e["summary"]
        return text[:400] + " " + e["location_name"]
    hits = [e for e in events if "drill" in shown_text(e).lower()]
    assert hits, "the fixture has drilling events"
    assert page.locator("#event-list .event-row").count() == min(60, len(hits)) and page.evaluate("document.getElementById('map-count').textContent").startswith(f"{len(hits)} event")
    page.click("#reset")
    page.wait_for_timeout(300)
    assert page.locator("#event-list .event-row").count() == min(60, len(events))
    page.close()


def test_tracker_draws_at_phone_width(browser, dist):
    page, problems = _open(browser, dist, "map.html", (390, 800))
    assert problems == []
    assert page.locator("#map canvas.maplibregl-canvas").count() == 1 and page.locator(".sr-label").count() == 10
    # the map comes first and the sidebar follows it
    assert page.evaluate("document.querySelector('.map-stage').getBoundingClientRect().top") < page.evaluate("document.querySelector('.side').getBoundingClientRect().top")
    page.close()


def _luma(css_rgb):
    """Gamma-encoded luma of a CSS rgb() string, enough to tell a dark plane from a light one."""
    r, g, b = [int(x) for x in re.findall(r"\d+", css_rgb)[:3]]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_public_face(browser, dist):
    """Ticket 27: the event tracker moved to map.html, the home page is the assertiveness map. Tickets 17–18: the programme banner heads every page; the tracker is a sidebar beside a full-height map on the site's white paper;
    inner pages are white with a kicker over the title; there is one colour scheme; and nothing on the
    site talks about the project's own progress — no pending move, no "pending", no "confirmation",
    no count of claimants or moves coded."""
    page, problems = _open(browser, dist, "map.html")
    assert problems == []
    assert page.locator(".site-head .masthead-img").count() == 1 and page.evaluate("document.querySelector('.masthead-img').getAttribute('src')").endswith("masthead.svg")
    assert page.evaluate("document.querySelector('.masthead-img').complete && document.querySelector('.masthead-img').naturalWidth > 0"), "the vector artwork loads"
    assert page.evaluate("[...document.fonts].some(f => f.family === 'Outfit' && f.status === 'loaded')")
    # ticket 18: the tracker is white like the rest of the site; only the navigation band and the banner's band are dark
    side_rgb, map_rgb, nav_rgb = page.evaluate("[getComputedStyle(document.querySelector('.side')).backgroundColor, getComputedStyle(document.getElementById('map')).backgroundColor, getComputedStyle(document.querySelector('.navband')).backgroundColor]")
    assert _luma(side_rgb) > 240 and _luma(map_rgb) > 230 and _luma(nav_rgb) < 80, (side_rgb, map_rgb, nav_rgb)
    assert nav_rgb == "rgb(5, 44, 89)", "the logo's navy"
    assert _luma(page.evaluate("getComputedStyle(document.querySelector('.side h1')).color")) < 60
    label = page.locator("#map-claimant-filter .check").first
    assert _luma(page.evaluate("(l) => getComputedStyle(l.querySelector('.check-label')).color", label.element_handle())) < 80
    assert "dark-en" not in page.content() and "positron" in page.content().lower(), "the light basemap"
    page.focus("#search")
    assert page.evaluate("getComputedStyle(document.getElementById('search')).outlineStyle") == "solid", "keyboard focus is visible inside the tracker"
    page.close()
    page, problems = _open(browser, dist, "methodology.html")
    assert problems == []
    assert page.locator(".site-head .masthead-img").count() == 1
    assert _luma(page.evaluate("getComputedStyle(document.body).backgroundColor")) > 250, "white article paper"
    assert page.evaluate("document.querySelector('main .kicker').compareDocumentPosition(document.querySelector('main h1')) & Node.DOCUMENT_POSITION_FOLLOWING")
    page.close()
    css = (dist / "assets/style.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme" not in css and "data-theme" not in css, "one colour scheme"
    # the words that would give the review state away, in any page's visible text; case pages carry the
    # data's own prose (a source may say "pending" or "in progress"), so they are held to the phrases only
    forbidden = re.compile(r"\bpending\b|\bconfirmation\b|flagged for the author|awaits the author|being built|work in progress|claimants coded|moves coded|coding is in progress|reviewed yet|not yet", re.I)
    forbidden_in_data_pages = re.compile(r"pending the author|author.s confirmation|flagged for the author|awaits the author", re.I)
    pending = [m["move_id"] for m in read_csv(DATA_DIR / "moves.csv") if m["status"] != "accepted"]
    assert pending, "the fixture data has a pending move to keep off the site"
    for path in dist.rglob("*.html"):   # the visible text; the inline data blocks carry the aggregates as data
        visible = re.sub(r"<script[^>]*>.*?</script>", "", path.read_text(encoding="utf-8"), flags=re.S)
        rule = forbidden_in_data_pages if path.parent.name == "cases" else forbidden
        assert not rule.search(visible), (path.relative_to(dist), rule.search(visible).group(0))
    assert "n_pending" not in (dist / "trends.html").read_text(encoding="utf-8"), "the review-state count stays in data/aggregates.json only"
    for path in (dist / "assets").glob("*.js"):
        assert "pending" not in path.read_text(encoding="utf-8").lower(), path.name
    for move_id in pending:
        assert not (dist / "cases" / f"{move_id}.html").exists()
        assert move_id not in (dist / "cases.html").read_text(encoding="utf-8")
        assert move_id not in (dist / "index.html").read_text(encoding="utf-8")


def test_nav_scrolls_rather_than_wraps_at_phone_width(browser, dist):
    page, problems = _open(browser, dist, "cases.html", viewport=(390, 800))
    assert problems == []
    nav = "document.querySelector('.nav')"
    assert page.evaluate(f"{nav}.scrollWidth > {nav}.clientWidth"), "the links overflow the row and scroll"
    assert page.evaluate(f"{nav}.getBoundingClientRect().height") < 60, "one row"
    assert not page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    # the last link is reachable: tabbing to it scrolls it into view
    for _ in range(12):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement && document.activeElement.textContent") == "Downloads":
            break
    assert page.evaluate("document.activeElement.textContent") == "Downloads"
    box = page.evaluate("(() => { const r = document.activeElement.getBoundingClientRect(); return [r.left, r.right]; })()")
    assert 0 <= box[0] and box[1] <= 390, box
    # from 1000px the tracker's name and every link share one thin row, nothing hidden or scrolled
    page.set_viewport_size({"width": 1024, "height": 800})
    page.wait_for_timeout(100)
    assert abs(page.evaluate(f"{nav}.getBoundingClientRect().top") - page.evaluate("document.querySelector('.navband').getBoundingClientRect().top")) < 3
    assert page.evaluate(f"{nav}.scrollWidth <= {nav}.clientWidth") and page.evaluate(f"{nav}.getBoundingClientRect().right") <= 1024
    assert page.evaluate("document.querySelector('.navband').getBoundingClientRect().height") <= 48
    page.close()


def test_overview_charts_and_controls(browser, dist):
    page, problems = _open(browser, dist, "trends.html")
    # one stacked chart for all claimants plus one per claimant with data
    assert page.locator('[data-chart="all-claimants"] svg').count() == 1
    assert page.locator('[data-chart="by-type"] svg').count() == 3
    # a claimant with no moves in the data has no panel and no chip (the page shows what is recorded, not the coding's state)
    assert page.locator('.figure.small[hidden]').count() == 4 and page.locator('#claimant-filter .chip[hidden]').count() == 4
    assert page.locator('[data-chart="by-type"] .empty').count() == 0
    # 357 columns worth of segments: China+Vietnam+Philippines across the years
    assert page.locator('[data-chart="all-claimants"] .seg').count() > 100
    # stack the main chart by type: four series, same totals as MAVD's all-countries chart
    page.locator('#stack-by input[value="type"]').check(force=True)
    page.wait_for_timeout(100)
    assert page.locator("#fig-all .legend .key").count() == 4
    assert "Use of force" in page.locator("#fig-all .legend").inner_text()
    page.locator('#stack-by input[value="claimant"]').check(force=True)
    page.wait_for_timeout(100)
    # filter: drop China and the legend and note follow (the overview's own chips, not the map's)
    page.locator('#claimant-filter .chip[data-code="CN"] input').uncheck(force=True)
    page.wait_for_timeout(100)
    assert page.locator("#filters-note").inner_text() == "2 of 3 claimants"   # of the claimants with moves on the page
    assert page.locator("#fig-CN").is_hidden()
    assert page.locator('#fig-all .legend .key').count() == 2   # the two shown claimants with moves; the legend never lists an uncoded one
    # table view twin
    page.locator('[data-toggle-table="fig-all"]').click()
    assert page.locator("#fig-all .table-view").is_visible()
    rows = page.locator("#fig-all .table-view tbody tr").count()
    assert rows == 46  # 1970..2015
    assert "213" in page.locator("#fig-all .table-view tfoot").inner_text()
    # table state survives a re-render (filter change) and the legend stays hidden
    page.locator('#claimant-filter .chip[data-code="CN"] input').check(force=True)
    page.wait_for_timeout(100)
    assert page.locator("#fig-all .table-view").is_visible()
    assert page.locator("#fig-all .legend").count() == 0
    assert "357" in page.locator("#fig-all .table-view tfoot").inner_text()
    # empty claimant panels have no table toggle
    assert page.locator('#fig-MY [data-toggle-table]').is_hidden()
    # hover tooltip appears on a column
    page.locator('[data-toggle-table="fig-all"]').click()
    page.locator('[data-chart="all-claimants"] .hit >> nth=41').scroll_into_view_if_needed()
    page.wait_for_timeout(100)   # a scroll hides the tooltip, so settle first
    page.hover('[data-chart="all-claimants"] .hit >> nth=41')
    page.wait_for_timeout(50)
    assert page.locator(".tooltip").is_visible()
    assert "2011" in page.locator(".tooltip").inner_text()
    assert problems == []
    page.close()


# ---- ticket 03: case browser and move detail ------------------------------

def _moves():
    return read_csv(DATA_DIR / "moves.csv")


def test_every_move_has_a_stable_page(dist):
    moves = [m for m in _moves() if m["status"] == "accepted"]   # a pending move has no page until it is accepted
    pages = sorted(p.stem for p in (dist / "cases").glob("*.html"))
    assert pages == sorted(m["move_id"] for m in moves)
    html = (dist / "cases/CN201105.html").read_text(encoding="utf-8")
    assert "China, 2011" in html and 'href="../assets/style.css"' in html


def test_case_page_content_matches_the_files(dist):
    m = next(m for m in _moves() if m["move_id"] == "VN197301")
    html = (dist / "cases/VN197301.html").read_text(encoding="utf-8")
    assert html_escape(m["description"][:60]) in html
    assert html.count('<time datetime="1973-') == 5          # five seed events, in date order
    assert html.index('datetime="1973-01-29"') < html.index('datetime="1973-08-14"')
    assert "29 January 1973" in html and html.count('<ul class="sources">') == 5   # a source per event
    assert 'href="#description"' in html                                            # seed sources link to the description
    assert 'class="sr is-on" data-loc="2"' in html and 'class="sr is-on" data-loc="5"' in html  # Paracels, Spratly NW
    assert html.count('class="sr is-on"') == 2
    assert not (dist / "cases/VN197304.html").exists()   # pending: not published (ticket 17)


def test_case_index_matches_the_files(dist):
    page = (dist / "cases.html").read_text(encoding="utf-8")
    inline = re.search(r'<script id="cases" type="application/json">(.*?)</script>', page, re.S)
    index = json.loads(inline.group(1))["cases"]
    moves = {m["move_id"]: m for m in _moves() if m["status"] == "accepted"}
    assert {c["id"] for c in index} == set(moves)
    c = next(c for c in index if c["id"] == "CN197401")
    assert c["t"] == ["force"] and 2 in c["s"] and "V" in c["g"] and c["y"] == 1974


def test_case_browser_filters(browser, dist):
    page, problems = _open(browser, dist, "cases.html")
    moves = [m for m in _moves() if m["status"] == "accepted"]   # the site publishes accepted moves only
    n_all = len(moves)
    assert page.locator("#count").inner_text() == f"{n_all} moves"
    assert page.locator("#case-list li").count() == n_all
    # free-text search
    expect = sum(1 for m in moves if "scarborough" in m["description"].lower())
    page.fill("#q", "Scarborough")
    page.wait_for_timeout(200)
    assert page.locator("#case-list li").count() == expect
    assert page.locator("#count").inner_text().startswith(f"{expect} of {n_all}")
    # claimant + type + year range
    page.fill("#q", "")
    page.locator('.chip[data-code="VN"] input').uncheck(force=True)
    page.locator('.chip[data-code="PH"] input').uncheck(force=True)
    page.locator('input[name="t"][value="force"]').check(force=True)
    page.fill("#y0", "1970")
    page.fill("#y1", "1990")
    page.wait_for_timeout(200)
    expect = sum(1 for m in moves if m["claimant"] == "CN" and m["force"] == "1" and 1970 <= int(m["year"]) <= 1990)
    assert expect > 0
    assert page.locator("#case-list li").count() == expect
    # sub-region and counterpart
    page.locator("#reset").click()
    page.select_option("#subregion", "1")
    page.select_option("#target", "V")
    page.wait_for_timeout(200)
    expect = sum(1 for m in moves if m["loc01_tonkin"] == "1" and any(len(d) == 2 and d[1] == "V" for d in m["dyads"].split()))
    assert page.locator("#case-list li").count() == expect
    # a result links to its page
    href = page.locator("#case-list li a").first.get_attribute("href")
    assert (dist / href).exists()
    # no match state
    page.fill("#q", "zzzz-no-such-text")
    page.wait_for_timeout(200)
    assert page.locator("#no-match").is_visible()
    assert problems == []
    page.close()


@pytest.mark.parametrize("move_id", ["CN197001", "CN197401", "PH199501", "VN201104", "VN197301", "CN201504", "PH201404"])
def test_case_pages_render_without_errors(browser, dist, move_id):
    page, problems = _open(browser, dist, f"cases/{move_id}.html", viewport=(390, 800))
    assert problems == []
    assert page.locator(".inset svg path").count() == 10
    assert not page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    page.close()


# ---- ticket 04: issues/domains and sub-regions pages -----------------------

def _count(moves, **flags):
    return sum(1 for m in moves if all(m[k] == v for k, v in flags.items()))


def test_trends_issues_and_domains_match_the_files(browser, dist):
    """Ticket 28: issues and domains are a section of Trends; the claimant chips scope them too."""
    page, problems = _open(browser, dist, "trends.html")
    moves = [m for m in _moves() if m["status"] == "accepted"]
    page.locator('[data-toggle-table="fig-issues-all"]').click()
    page.wait_for_timeout(100)
    row = page.locator("#fig-issues-all .table-view tbody tr", has_text="1988").first.inner_text().split("\t")
    header = page.locator("#fig-issues-all .table-view thead th").all_inner_texts()
    assert row[header.index("Energy")] == str(_count(moves, year="1988", energy="1"))
    assert row[header.index("Military")] == str(_count(moves, year="1988", military="1"))
    page.locator('[data-toggle-table="fig-domains-all"]').click()
    page.wait_for_timeout(100)
    row = page.locator("#fig-domains-all .table-view tbody tr", has_text="1994").first.inner_text().split("\t")
    header = page.locator("#fig-domains-all .table-view thead th").all_inner_texts()
    assert row[header.index("Diplomatic")] == str(_count(moves, year="1994", diplomatic="1"))
    page.locator('.chip[data-code="CN"] input').uncheck(force=True)
    page.wait_for_timeout(100)
    row = page.locator("#fig-issues-all .table-view tbody tr", has_text="1988").first.inner_text().split("\t")
    header = page.locator("#fig-issues-all .table-view thead th").all_inner_texts()
    assert row[header.index("Military")] == str(sum(1 for m in moves if m["year"] == "1988" and m["military"] == "1" and m["claimant"] != "CN"))
    assert problems == []
    page.close()


def test_trends_subregions_section(browser, dist):
    """Ticket 28: the sub-region charts are a section of Trends, scoped by the same chips."""
    page, problems = _open(browser, dist, "trends.html")
    moves = [m for m in _moves() if m["status"] == "accepted"]
    assert page.locator('[data-chart="years"][data-dim="subregion"] svg').count() == 10
    for c in ("CN", "VN"):   # Philippines alone
        page.locator(f'.chip[data-code="{c}"] input').uncheck(force=True)
    page.wait_for_timeout(150)
    fill = page.locator('[data-chart="years"][data-dim="subregion"] .seg').first.get_attribute("fill")
    assert fill.lower() == page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--ph').trim()").lower(), "one colour per selection"
    page.locator('[data-toggle-table="fig-loc-type"]').click()
    page.wait_for_timeout(100)
    header = page.locator("#fig-loc-type .table-view thead th").all_inner_texts()
    row = page.locator("#fig-loc-type .table-view tbody tr", has_text="6 Spratly NE").first.inner_text().split("\t")
    assert row[header.index("Total")] == str(sum(1 for m in moves if m["claimant"] == "PH" and m["loc06_spratly_ne"] == "1"))
    assert problems == []
    page.close()


def test_the_merged_pages_redirect_to_trends(dist):
    for old, anchor in (("issues-domains.html", "#issues"), ("subregions.html", "#subregions")):
        html = (dist / old).read_text(encoding="utf-8")
        assert f'content="0; url=trends.html{anchor}"' in html and f'href="trends.html{anchor}"' in html
    trends = (dist / "trends.html").read_text(encoding="utf-8")
    assert 'id="issues"' in trends and 'id="subregions"' in trends


def test_periods_extend_with_the_years():
    from web.build import periods

    labels = lambda ys: [p["label"] for p in periods(ys)]
    assert labels(list(range(1970, 2016))) == ["All years", "1970", "1971–75", "1976–80", "1981–85", "1986–90", "1991–95",
                                                "1996–00", "2001–05", "2006–10", "2011–15"]
    assert labels(list(range(1970, 2027)))[-3:] == ["2016–20", "2021–25", "2026"]
    assert labels(list(range(1970, 2023)))[-1] == "2021–22"
    assert periods(list(range(1970, 2027)))[-1]["years"] == [2026]
    assert sum(len(p["years"]) for p in periods(list(range(1970, 2027)))[1:]) == 57   # every year in exactly one bin


# ---- ticket 08: event map -------------------------------------------------

PNG_1x1 = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da6364f8cfc000000301010018dd8db00000000049454e44ae426082")




def _open_map(browser, dist, viewport=(1280, 900)):
    """The map page with the basemap answered locally: the TileJSON names a stub tile URL that
    returns no content, as do fonts and sprites. The test is offline except for those stubs."""
    ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
    ctx.add_init_script("try { localStorage.setItem('scs-curtain-seen', '1'); } catch (e) {}")
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(("console", m.type, m.text)) if m.type in ("error", "warning") and not HEADLESS_NOISE.search(m.text) else None)
    page.on("pageerror", lambda e: problems.append(("pageerror", str(e))))
    page.on("requestfailed", lambda r: None if _stale_tile(r) else problems.append(("requestfailed", r.url)))
    tiles = []
    page.route("https://tiles.openfreemap.org/**", _tile_stub(tiles))
    page.goto((dist / "map.html").resolve().as_uri())
    page.wait_for_timeout(1200)
    page.on("close", lambda _: ctx.close())
    return page, problems, tiles


def test_map_data_matches_the_validator(dist):
    from pipeline.validate import event_aggregates
    data = json.loads((dist / "data/events.json").read_text(encoding="utf-8"))
    expected = event_aggregates(read_csv(DATA_DIR / "events.csv"), read_csv(DATA_DIR / "moves.csv"))
    assert data["counts"] == expected
    assert len(data["events"]) == expected["n_events"]
    # every event drawn is accepted, belongs to an accepted move, and is either a point or counted on sub-regions
    moves = {m["move_id"]: m for m in read_csv(DATA_DIR / "moves.csv")}
    for e in data["events"]:
        assert moves[e["m"]]["status"] == "accepted"
        assert e["sr"] and all(s in {str(i) for i in range(1, 11)} for s in e["sr"])    # every event sits on a sub-region
    assert [f["properties"]["n"] for f in data["subregions"]["features"]] == list(range(1, 11))



def test_every_name_on_the_maps_is_english(dist):
    """Ticket 32: feature labels, the reefs a move names, event places and sub-region names, all in English."""
    from pipeline.gazetteer import is_english_name
    data = json.loads((dist / "data/events.json").read_text(encoding="utf-8"))
    names = [f["properties"]["n"] for f in data["assert"]["gazetteer"]["features"]]
    names += [f["n"] for f in data["assert"]["features"].values()]
    names += [e["n"] for e in data["events"] if e["n"]]
    names += list(data["subregion_names"].values()) + [f["properties"]["name"] for f in data["subregions"]["features"]]
    bad = sorted({n for n in names if not is_english_name(n)})
    assert not bad, bad


@pytest.mark.parametrize("viewport", [(1280, 900), (390, 800)])
def test_map_renders_offline_without_errors(browser, dist, viewport):
    from pipeline.validate import event_aggregates
    page, problems, tiles = _open_map(browser, dist, viewport)
    expected = event_aggregates(read_csv(DATA_DIR / "events.csv"), read_csv(DATA_DIR / "moves.csv"))
    assert page.locator("#map canvas.maplibregl-canvas").count() == 1 and page.locator(".sr-label").count() == 10
    assert any(t.rstrip("/").endswith("/planet") for t in tiles), "basemap requested from the attribution-compliant provider"
    assert "OpenFreeMap" in page.inner_text("#map .maplibregl-ctrl-attrib") and "OpenStreetMap" in page.inner_text("#map .maplibregl-ctrl-attrib")
    text = page.evaluate("document.getElementById('map-count').textContent")
    data = page.evaluate("(() => { const d = document.getElementById('map-count').dataset; return [+d.placed, +d.bySubregion]; })()")
    assert text.startswith(f"{expected['n_events']} events through ") and data == [expected['n_points'], expected['n_events']], (text, data)
    assert "placed" not in text and "by sub-region" not in text, "the count line is the count and the period only (2026-11-24)"
    # the sub-region counts on the map are the validator's, summed over claimants
    shown = {}
    for el in page.locator("[role='button'][tabindex='0']").element_handles():
        title = el.get_attribute("title") or ""
        mm = re.search(r"^(\d+) events? in sub-region (\d+) ", title)
        if mm:
            shown[mm.group(2)] = int(mm.group(1))
    want = {}
    for c in expected["by_claimant"].values():
        for sr, n in c["subregions"].items():
            if n:
                want[sr] = want.get(sr, 0) + n
    assert shown == want
    assert page.locator(".evt, .sr-count").count() == len(want) + len({(e.get("lat"), e.get("lon")) for e in json.loads((dist / "data/events.json").read_text(encoding="utf-8"))["events"] if "lat" in e})
    assert not problems, problems
    page.close()


@pytest.fixture(scope="module")
def dist_placed(tmp_path_factory):
    """A build from a data copy with four placed events (two stacked at one feature, one point, one
    unplaced) so the point-marker code is exercised on a known set: the data's own coordinates (Chubb's
    dated incidents placed at their move's feature, ticket 41) are cleared in the copy."""
    import csv
    import shutil
    d = tmp_path_factory.mktemp("placed") / "data"
    shutil.copytree(DATA_DIR, d, ignore=shutil.ignore_patterns("raw"))
    rows = list(csv.DictReader(open(d / "events.csv", newline="", encoding="utf-8")))
    for r in rows:
        if r["lat"]:
            r["lat"] = r["lon"] = ""
            r["location_precision"] = "subregion" if r["subregion"] else "unknown"
    cols = list(rows[0])
    extra = [("CN201201", "2012-04-10", "Scarborough Shoal", "15.18000", "117.77000", "4", "feature", "day", "Standoff begins at <b>Scarborough</b> Shoal."),
             ("CN201201", "2012-05-15", "Scarborough Shoal", "15.18000", "117.77000", "4", "feature", "day", "Fishing ban extended to the shoal."),
             ("CN201401", "2014-05-02", "south of Triton Island", "15.90000", "111.20000", "2", "point", "month", "HYSY 981 rig placed."),
             ("PH201301", "2013-01-22", "Manila", "", "", "", "unknown", "year", "Arbitration filed.")]
    for i, (m, ds, n, lat, lon, sr, lp, dp, summary) in enumerate(extra):
        rows.append({c: "" for c in cols} | {"event_id": f"{m}-T{i}", "move_id": m, "claimant": m[:2], "date_start": ds, "date_end": "",
                     "date_precision": dp, "lat": lat, "lon": lon, "location_name": n, "location_precision": lp, "subregion": sr,
                     "summary": summary, "status": "accepted", "harvest_run_id": "test", "reviewer": "t", "review_date": "2026-10-15"})
    with open(d / "events.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    out = tmp_path_factory.mktemp("dist-placed")
    build(d, out, build_date="2026-01-01")
    return out


def test_map_points_stack_open_and_follow_precision(browser, dist_placed):
    page, problems, _ = _open_map(browser, dist_placed)
    assert page.evaluate("document.getElementById('map-count').dataset.placed") == "3"
    # the points show only zoomed in; far out the sub-region counts carry every event
    assert page.locator(".evt:visible").count() == 0 and page.locator(".sr-count:visible").count() >= 1
    for _ in range(3):
        page.locator("#map .maplibregl-ctrl-zoom-in").click()
        page.wait_for_timeout(400)
    assert page.locator(".evt:visible").count() == 2
    # two events at one feature stack into one hollow marker carrying their count; the point event is filled
    evts = page.locator(".evt")
    assert evts.count() == 2
    stacked = page.locator(".evt.feature")
    assert stacked.count() == 1 and stacked.inner_text() == "2"
    assert page.locator(".evt:not(.feature)").inner_text() == ""
    # keyboard: the marker is a focusable button; Enter opens the popup, summaries are text not HTML
    stacked.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(300)
    popup = page.locator(".evt-popup")
    assert popup.locator(".event-row").count() == 2
    assert "<b>" in popup.inner_text() and popup.locator("b").count() == 0
    assert (dist_placed / popup.locator("a.case-id").first.get_attribute("href")).exists()
    # a month-precision event is in view for its whole month, a year-precision one all year
    def counts_at(year, month_no):
        page.select_option("#window", "1")
        page.fill("#month", str((year - 1970) * 12 + month_no - 1))
        page.dispatch_event("#month", "input")
        page.wait_for_timeout(250)
        return tuple(page.evaluate("(() => { const d = document.getElementById('map-count').dataset; return [+d.placed, +d.bySubregion]; })()"))
    assert counts_at(2014, 5)[0] == 1 and counts_at(2014, 5 + 1)[0] == 0          # the rig, dated to May 2014
    assert counts_at(2013, 11)[1] >= 1 and counts_at(2013, 1)[1] >= 1            # the filing, dated to 2013
    assert counts_at(2012, 4)[0] == 1 and counts_at(2012, 4 + 1)[0] == 1 and counts_at(2012, 6)[0] == 0   # two day-dated events
    counts_at(2014, 5)
    assert page.inner_text("#time-label") == "May 2014" and page.get_attribute("#month", "aria-valuetext") == "May 2014"
    # the move page shows each event's place (spec story 3)
    case = (dist_placed / "cases/CN201201.html").read_text(encoding="utf-8")
    assert "Scarborough Shoal (15.18000, 117.77000, at the named feature) · sub-region 4 Central-East" in case
    assert "Manila" in (dist_placed / "cases/PH201301.html").read_text(encoding="utf-8")
    assert page.locator(".sr-label[tabindex]").count() == 0, "labels are not tab stops"
    assert page.locator(".sr-label").count() == 10
    # the basemap style asks for English names in the Latin alphabet
    style = json.loads(re.search(r'<script id="mapstyle" type="application/json">(.*?)</script>', (dist_placed / "map.html").read_text(encoding="utf-8"), re.S).group(1))
    for layer in style["layers"]:
        tf = layer.get("layout", {}).get("text-field")
        if tf and "name" in json.dumps(tf):
            assert tf[:2] == ["coalesce", ["get", "name:en"]], layer["id"]
    assert not problems, problems
    page.close()


def test_map_time_window_and_filters(browser, dist):
    page, problems, _ = _open_map(browser, dist)
    events = read_csv(DATA_DIR / "events.csv")
    moves = {m["move_id"]: m for m in read_csv(DATA_DIR / "moves.csv")}
    shown = [e for e in events if e["status"] == "accepted" and moves.get(e["move_id"], {}).get("status") == "accepted"]
    # the year window ending Dec 2014 holds the events that overlap 2014
    first = int(page.get_attribute("#month", "min") or 0)
    page.select_option("#window", "12")
    page.fill("#month", str((2014 - 1970) * 12 + 11))
    page.dispatch_event("#month", "input")
    page.wait_for_timeout(300)
    in_2014 = [e for e in shown if e["date_start"][:4] <= "2014" and (e["date_end"] or e["date_start"])[:4] >= "2014"]
    assert page.evaluate("document.getElementById('map-count').textContent").startswith(f"{len(in_2014)} events January 2014 to December 2014")
    # unchecking a claimant removes its events; a type filter keeps only moves of that type
    page.uncheck('input[name="claimant"][value="VN"]', force=True)
    page.wait_for_timeout(300)
    assert page.evaluate("document.getElementById('map-count').textContent").startswith(f"{len([e for e in in_2014 if e['claimant'] != 'VN'])} events")
    page.click("#reset")
    page.check('input[name="t"][value="coercive"]', force=True)
    page.wait_for_timeout(300)
    coercive = [e for e in shown if moves[e["move_id"]]["coercive"] == "1"]
    assert page.evaluate("document.getElementById('map-count').textContent").startswith(f"{len(coercive)} events through")
    # the sidebar names every event in view with a link to its move
    rows = page.locator("#event-list .event-row")
    assert rows.count() == min(len(coercive), 400)
    href = rows.first.locator("a.case-id").get_attribute("href")
    assert href and (dist / href).exists()
    # a sub-region count opens a popup listing its events
    page.locator(".sr-count").first.click()
    page.wait_for_timeout(300)
    assert page.locator(".evt-popup .event-row").count() >= 1
    assert not problems, problems
    page.close()


# ---- ticket 11: new claimants need no special-casing -------------------

def test_new_claimants_render_everywhere_without_special_casing(tmp_path):
    """A project-coded Malaysian, Indonesian and Taiwanese move each, with an event: every page
    counts and lists them exactly as it does the original three."""
    import csv
    import shutil
    from pipeline import schema
    from pipeline.validate import validate
    from tests.conftest import RAW_MAVD, RAW_XLSX
    d = tmp_path / "data"
    shutil.copytree(DATA_DIR, d, ignore=shutil.ignore_patterns("raw"))
    new_moves, new_events, new_sources = [], [], []
    for code, year, feat, sr in (("MY", "2021", "coercive", "loc10_far_south"), ("ID", "2016", "coercive", "loc10_far_south"), ("TW", "2016", "demonstrative", "loc05_spratly_nw")):
        m = {c: "" for c in schema.TABLES["moves"]}
        m.update(move_id=f"{code}{year}01", claimant=code, year=year, instance_no="01", status="accepted", coded_by="project", coder="T",
                 coding_date="2026-10-18", data_version=schema.DATASET_VERSION, dyads=f"{ {'MY': 'M', 'ID': 'I', 'TW': 'R'}[code] }C",
                 intensification_criterion="novelty", description=f"Test move for {code}.", ongoing_through=year)
        for f in schema.TYPE_FLAGS + schema.DOMAIN_FLAGS + schema.ISSUE_FLAGS + schema.SUBREGION_FLAGS:
            m[f] = "1" if f in (feat, "physical", "military", sr) else "0"
        new_moves.append(m)
        e = {c: "" for c in schema.TABLES["events"]}
        e.update(event_id=f"{code}{year}01-T1", move_id=m["move_id"], claimant=code, date_start=f"{year}-06-01", date_end=f"{year}-06-01",
                 date_precision="day", summary=f"Test event for {code}.", status="accepted", harvest_run_id="test", extractor="t@prompt-x",
                 suggested_type=feat, reviewer="T", review_date="2026-10-18", location_precision="unknown")
        new_events.append(e)
        new_sources.append({**{c: "" for c in schema.TABLES["sources"]}, "source_id": e["event_id"] + "-S01", "event_id": e["event_id"],
                            "url": "https://example.org/s", "title": "s", "publisher": "p", "accessed_date": "2026-10-18", "excerpt": "x"})
    for name, rows in (("moves", new_moves), ("events", new_events), ("sources", new_sources)):
        with open(d / f"{name}.csv", "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=schema.TABLES[name], lineterminator="\n")
            w.writerows(rows)
    assert validate(d, RAW_XLSX, RAW_MAVD) == []
    out = tmp_path / "dist"
    build(d, out, build_date="2026-10-18")
    agg = json.loads((out / "data/aggregates.json").read_text(encoding="utf-8"))
    assert agg["by_claimant"]["MY"]["totals"]["total"] == 1 and agg["by_claimant"]["TW"]["years"]["2016"]["demonstrative"] == 1
    assert agg["years"][-1] == 2021
    for mid in ("MY202101", "ID201601", "TW201601"):
        page_html = (out / f"cases/{mid}.html").read_text(encoding="utf-8")
        assert "project" in page_html.lower() and "Test move for" in page_html
    index = json.loads(re.search(r'<script id="cases"[^>]*>(.*?)</script>', (out / "cases.html").read_text(encoding="utf-8"), re.S).group(1).replace("<\\/", "</"))
    assert {c["c"] for c in index["cases"]} >= {"MY", "ID", "TW"}
    assert {c["cb"] for c in index["cases"] if c["c"] in ("MY", "ID", "TW")} == {"project"}   # labelled as project coding in the list
    events = json.loads((out / "data/events.json").read_text(encoding="utf-8"))
    assert {e["c"] for e in events["events"]} >= {"MY", "ID", "TW"}
    # the overview's chart data carries the new claimants' columns and the extended year axis
    agg_html = (out / "trends.html").read_text(encoding="utf-8")
    inline = json.loads(re.search(r'<script id="agg"[^>]*>(.*?)</script>', agg_html, re.S).group(1).replace("<\\/", "</"))
    assert inline["by_claimant"]["MY"]["years"]["2021"]["coercive"] == 1 and inline["years"][-1] == 2021



def test_the_first_screen_is_the_assertiveness_map(browser, dist):
    """Ticket 27: under the masthead and the menu, the map of the latest five-year window fills the first
    screen; the slider, the claimant choice and the details come on scrolling; the event tracker follows."""
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    assert problems == []
    assert page.locator("#amap canvas.maplibregl-canvas").count() == 1
    assert page.locator(".site-head .masthead").count() == 1, "the masthead heads the home page too (2026-11-24)"
    assert page.locator("#map").count() == 0, "one map on the home page"
    scope = page.locator(".amap-caption .amap-scope")
    assert scope.is_visible() and "not every incident" in scope.inner_text() and scope.locator("a").get_attribute("href") == "methodology.html#what", "what the map measures (2026-11-24)"
    stage_top = page.evaluate("document.querySelector('.amap-stage').getBoundingClientRect().top")
    assert stage_top < 260 and page.evaluate("document.getElementById('amap-explore').getBoundingClientRect().top") >= 880, "the panel waits below the fold"
    # it opens on the latest five years with moves (the fixture's data ends in 2015); the slider reaches the build year
    assert page.locator("#amap-when").inner_text() == "2011–2015" and page.locator("#amap-year").get_attribute("max") == "2026"
    assert "Degree of assertiveness" in page.locator(".amap-legend").inner_text()
    page.evaluate("(() => { const s = document.getElementById('amap-year'); s.value = '2015'; s.dispatchEvent(new Event('input')); })()")
    assert page.locator("#amap-when").inner_text() == "2011–2015"
    assert page.locator("#amap-detail .amap-sum").inner_text().split(" ")[0].isdigit()
    assert page.locator(".amap-count").count() == 10
    page.locator(".amap-count").nth(5).click()   # 6 Spratly NE: zooms in, the features its moves name appear
    page.wait_for_timeout(1200)
    assert page.locator("#amap-detail .amap-detail-head").inner_text().startswith("6 ") and page.locator(".amap-feat-dot:visible").count() >= 1
    page.locator(".amap-feat-dot:visible").first.click()
    assert page.locator("#amap-detail .amap-move").count() >= 1
    page.select_option("#amap-claimant", "VN")
    assert page.locator("#amap-who").inner_text() == "Vietnam"
    # the filters narrow the moves: coercive and force only, directed at China
    page.uncheck("input[name='amap-type'][value='declarative']")
    page.uncheck("input[name='amap-type'][value='demonstrative']")
    page.select_option("#amap-target", "C")
    assert page.locator("#amap-who").inner_text() == "Vietnam · coercive, use of force only · directed at China (PRC)"
    assert page.locator("#amap-timeline svg rect").count() > 40
    # the stage sticks while the panel scrolls over it
    page.evaluate("document.getElementById('amap-explore').scrollIntoView()")
    page.wait_for_timeout(200)
    assert abs(page.evaluate("document.querySelector('.amap-stage').getBoundingClientRect().top")) < 2
    page.close()


def test_a_view_of_the_map_has_its_own_address(browser, dist):
    """Ticket 27: the window, the claimant and the sub-region are in the address, so a view can be sent."""
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    page.goto((dist / "index.html").resolve().as_uri() + "#y2014-vn-s4")
    page.reload()   # read on load as well as on a change of address
    page.wait_for_timeout(1200)
    assert problems == []
    assert page.locator("#amap-when").inner_text() == "2010–2014" and page.locator("#amap-who").inner_text() == "Vietnam"
    assert page.locator("#amap-detail .amap-detail-head").inner_text().startswith("4 ")
    assert page.locator(".amap-decade").count() >= 5 and page.locator(".amap-moment").count() == 0
    page.check("input[name='amap-mode'][value='cumulative']")
    assert page.locator("#amap-when").inner_text() == "1970–2014" and page.locator(".amap-arrow").count() == 0
    assert page.evaluate("location.hash") == "#y2014-c-vn-s4"
    page.check("input[name='amap-mode'][value='window']")
    page.select_option("#amap-claimant", "ALL")
    assert page.evaluate("location.hash") == "#y2014-s4"
    # the reference lines are off until asked for, and go into the address
    assert page.evaluate("document.getElementById('amap-line-dashline').checked") is False
    page.click("label:has(#amap-line-dashline)")
    assert page.evaluate("location.hash") == "#y2014-l-d-s4"
    assert "Andrew Chubb's coding (MATS)" not in page.locator("#amap-explore").inner_text()
    page.close()


def test_the_map_scores_match_the_reference(browser, dist):
    """Ticket 27: the page computes its scores from the moves; with every move counted in full on each of
    its sub-regions they equal web.build.window_scores."""
    from web.build import window_scores
    moves = read_csv(DATA_DIR / "moves.csv")
    ref = window_scores(moves, 1970, 2026)["scores"]["ALL"]["2014"]
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    page.goto((dist / "index.html").resolve().as_uri() + "#y2014")
    page.reload()
    page.wait_for_timeout(1200)
    page.click("label:has(#amap-shared)")   # the switch off: every move in full on each of its sub-regions
    assert not page.is_checked("#amap-shared")
    for n in (2, 6):
        page.evaluate(f"location.hash = '#y2014-s{n}'")
        page.wait_for_timeout(300)
        text = page.locator("#amap-detail .amap-sum").inner_text()
        assert f"score {ref[n - 1]};" in text, (n, ref[n - 1], text)
    assert problems == []
    page.close()


def test_the_map_zooms_in_a_little_and_back_out_on_scrolling(browser, dist):
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    zoom = lambda: float(page.get_attribute("#amap", "data-zoom"))
    start = zoom()
    page.evaluate("(() => { const s = document.querySelector('.amap'); window.scrollTo(0, (s.offsetHeight - innerHeight) / 2); })()")
    page.wait_for_timeout(400)
    middle = zoom()
    page.evaluate("(() => { const s = document.querySelector('.amap'); window.scrollTo(0, s.offsetTop + s.offsetHeight - innerHeight); })()")
    page.wait_for_timeout(400)
    assert middle > start + 0.3 and abs(zoom() - start) < 0.1, (start, middle, zoom())
    assert problems == []
    page.close()



def test_the_zoom_hint_never_covers_the_map_on_a_desktop(browser, dist):
    """Ticket 29: MapLibre's ctrl + scroll hint is hidden on a desktop, and never veils the map."""
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    page.mouse.move(700, 500)
    page.mouse.wheel(0, 200)
    page.wait_for_timeout(150)
    assert page.evaluate("(() => { const m = document.querySelector('#amap .maplibregl-desktop-message'); return !m || getComputedStyle(m).display === 'none'; })()")
    assert page.evaluate("(() => { const s = document.querySelector('#amap .maplibregl-cooperative-gesture-screen'); return !s || getComputedStyle(s).backgroundColor === 'rgba(0, 0, 0, 0)'; })()")
    assert problems == []
    page.close()


def test_the_home_page_lists_the_latest_moves_under_the_caption(browser, dist):
    """Option H5 (2026-11-24), a rollover: under the map's caption a slim "Latest moves" bar with the newest
    date; it opens under the pointer, or on click, to the newest moves, each a link to its case page."""
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    bar = page.locator("#amap-latest")
    assert bar.get_attribute("open") is None and page.locator(".amap-latest-list").is_hidden(), "closed at first"
    cap = page.evaluate("document.querySelector('.amap-caption').getBoundingClientRect().bottom")
    box = page.evaluate("(() => { const r = document.getElementById('amap-latest').getBoundingClientRect(); return [r.top, r.left, r.height]; })()")
    assert box[0] > cap and box[1] < 40 and box[2] <= 44, ("a slim bar under the caption, at the left", box)
    page.hover("#amap-latest summary")
    page.wait_for_timeout(200)
    items = page.locator(".amap-latest-list li")
    assert page.locator(".amap-latest-list").is_visible() and 1 <= items.count() <= 4, "open under the pointer"
    assert page.evaluate("document.getElementById('amap-latest').getBoundingClientRect().bottom") < page.evaluate("document.querySelector('.amap-cue').getBoundingClientRect().top")
    hrefs = page.eval_on_selector_all(".amap-latest-list a", "els => els.map(a => a.getAttribute('href'))")
    assert all((dist / h).exists() for h in hrefs), hrefs
    assert all(" · " in d for d in page.eval_on_selector_all(".amap-latest-meta", "els => els.map(e => e.textContent)"))
    page.mouse.move(900, 600)
    page.wait_for_timeout(200)
    assert bar.get_attribute("open") is None, "closed again when the pointer leaves"
    assert problems == []
    page.locator(".amap-count").nth(5).click()
    page.wait_for_timeout(1200)
    assert bar.is_hidden(), "zoomed in, the bar steps aside"
    page.close()
    page, problems = _open(browser, dist, "index.html", (390, 800))
    page.locator("#amap-latest summary").click()
    assert page.locator(".amap-latest-list").is_visible(), "a tap opens it on a phone"
    page.close()


def test_the_masthead_and_the_thin_menu_band(browser, dist):
    """Option C (2026-11-24): on every page a thin masthead, the logo and the programme's name on the sea blue
    and the banner's reefs at the right, a link home; the menu band below has no logo and is one thin row."""
    for name in ("trends.html", "index.html", "cases.html"):
        page, problems = _open(browser, dist, name, (1440, 900))
        head = page.evaluate("(() => { const r = document.querySelector('.masthead').getBoundingClientRect(); return [r.top, r.height]; })()")
        assert head[0] == 0 and 60 <= head[1] <= 92, (name, head)
        assert page.locator(".masthead .masthead-logo").count() == 1 and page.locator(".navband img").count() == 0, "the logo once, in the masthead"
        assert page.locator(".masthead").get_attribute("href").endswith("index.html")
        assert "Research Initiative" in page.locator(".masthead-name").inner_text()
        assert page.evaluate("document.querySelector('.navband').getBoundingClientRect().height") <= 44, "one thin row"
        assert problems == []
        page.close()
    page, problems = _open(browser, dist, "trends.html", (390, 800))
    assert page.evaluate("document.querySelector('.masthead').getBoundingClientRect().height") <= 66
    assert not page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    assert problems == []
    page.close()


def test_the_home_page_opens_with_a_curtain_once(browser, dist):
    page, problems = _open(browser, dist, "index.html", (1440, 900), curtain=True)
    assert page.evaluate("!document.getElementById('curtain').hidden")
    # it fills the screen with the logo and the title in view
    box = page.evaluate("(() => { const r = document.querySelector('#curtain img').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()")
    left, top, width, height = box
    assert left + 0.008 * width >= -1 and left + 0.75 * width <= 1441, box
    assert height >= 0.85 * 900, box
    page.wait_for_timeout(2900)
    assert page.evaluate("document.getElementById('curtain').hidden"), "it lifts by itself"
    page.reload()
    page.wait_for_timeout(400)
    assert page.evaluate("document.getElementById('curtain').hidden"), "and not again for the same reader"
    assert problems == []
    page.close()



def test_the_scroll_zoom_carries_on_after_a_manual_zoom(browser, dist):
    """Ticket 30: zooming by hand first moves the base the scroll works from; the effect is kept."""
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    zoom = lambda: float(page.get_attribute("#amap", "data-zoom"))
    page.locator("#amap .maplibregl-ctrl-zoom-in").click()
    page.wait_for_timeout(800)
    manual = zoom()
    page.evaluate("(() => { const s = document.querySelector('.amap'); window.scrollTo(0, (s.offsetHeight - innerHeight) / 2); })()")
    page.wait_for_timeout(500)
    assert zoom() > manual + 0.3, (manual, zoom())
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    assert abs(zoom() - manual) < 0.1, (manual, zoom())
    assert problems == []
    page.close()


def test_feature_pages(dist):
    """Tickets 35 and 36: a page per reef, shoal or island a move is placed at or a claimant holds, linked
    from the map's data; it lists the moves placed there and who holds it."""
    data = json.loads((dist / "data/events.json").read_text(encoding="utf-8"))
    feats = data["assert"]["features"]
    paged = {k: f["p"] for k, f in feats.items() if not k.startswith("ev:")}
    assert paged and all((dist / "features" / f"{p}.html").exists() for p in paged.values())
    assert all(re.fullmatch(r"[a-z0-9-]+", p) for p in paged.values())          # ASCII addresses, also for Chinese ids
    html = (dist / "features" / "second-thomas-shoal.html").read_text(encoding="utf-8")
    assert "Philippines</span> holds it since 1999" in html and html.count('href="../cases/') >= 5
    assert "仁爱礁" in html                                                     # its names in the other languages
    woody = (dist / "features" / "woody-island.html").read_text(encoding="utf-8")
    assert "China</span> holds it since 1974" in woody and "As part of the Paracels" in woody
    index = (dist / "features.html").read_text(encoding="utf-8")
    assert all(f'href="features/{p}.html"' in index for p in paged.values())
    held = {h["n"]: h for h in data["assert"]["held"]}
    assert held["Taiping Island"]["h"] == ["TW"] and held["Paracel Islands"]["g"] == 1 and "Louisa Reef" not in held
    case = (dist / "cases" / "PH199902.html").read_text(encoding="utf-8")
    assert 'href="../features/second-thomas-shoal.html"' in case


def test_the_map_shows_who_holds_what_and_links_features(browser, dist):
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    page.goto((dist / "index.html").resolve().as_uri() + "#y2020-c-f-second-thomas-shoal")
    page.reload()
    page.wait_for_timeout(1200)
    assert problems == []
    detail = page.locator("#amap-detail")
    assert detail.locator(".amap-detail-head").inner_text().startswith("Second Thomas Shoal")
    assert "held by Philippines" in detail.inner_text()
    assert detail.locator(".amap-feature-link a").get_attribute("href") == "features/second-thomas-shoal.html"
    page.click("label:has(#amap-line-held)")
    assert page.evaluate("location.hash") == "#y2020-c-l-h-f-second-thomas-shoal"
    page.close()


def test_the_selected_sub_region_shows_its_history(browser, dist):
    """Ticket 37: a selected sub-region's panel carries its score over every window, on the map's scale;
    a click on the chart moves the map to that window."""
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    page.goto((dist / "index.html").resolve().as_uri() + "#y2014-s6")
    page.reload()
    page.wait_for_timeout(1200)
    assert problems == []
    svg = page.locator("#amap-detail .amap-history svg")
    assert svg.count() == 1 and "Score of sub-region 6" in svg.get_attribute("aria-label")
    box = svg.bounding_box()
    svg.click(position={"x": 4, "y": box["height"] / 2})   # the far left: the first window
    page.wait_for_timeout(300)
    assert page.evaluate("location.hash").startswith("#y1974")
    page.close()


def test_one_small_map_per_claimant(browser, dist):
    """Ticket 38: a small map per claimant for the window shown, on one scale; a click shows that claimant
    on the main map, and a second click all claimants again."""
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    page.goto((dist / "index.html").resolve().as_uri() + "#y2014")
    page.reload()
    page.wait_for_timeout(1200)
    assert problems == []
    maps = page.locator("#amap-claimants .amap-claimant-map")
    assert maps.count() == len(read_csv(DATA_DIR / "claimants.csv"))
    vn = page.locator("#amap-claimants .amap-claimant-map[data-code='VN']")
    vn.click()
    assert page.evaluate("location.hash") == "#y2014-vn" and page.locator("#amap-who").inner_text() == "Vietnam"
    page.locator("#amap-claimants .amap-claimant-map[data-code='VN']").click()
    assert page.evaluate("location.hash") in ("", "#y2014")
    page.close()


def test_cite_download_and_embed_a_view(browser, dist):
    """Ticket 39: the view's citation names the window, the claimant and the dataset version and ends
    with its link; the image downloads as a PNG; the embed code opens the same view in embed mode,
    which shows the map alone with a link back."""
    page, problems = _open(browser, dist, "index.html", (1440, 900))
    page.goto((dist / "index.html").resolve().as_uri() + "#y2014-vn")
    page.reload()
    page.wait_for_timeout(1200)
    page.locator("#amap-cite-box summary").click()
    page.wait_for_function("document.getElementById('amap-cite').value.length > 0")
    cite = page.locator("#amap-cite").input_value()
    assert "map view: Assertive moves, 2010–2014; Vietnam" in cite and "Dataset version " in cite and "#y2014-vn (accessed " in cite
    embed = page.locator("#amap-embed").input_value()
    assert embed.startswith('<iframe src="') and "?embed=1#y2014-vn" in embed
    with page.expect_download() as d:
        page.click("#amap-png")
    path = d.value.path()
    assert d.value.suggested_filename == "scs-tracker-y2014-vn.png" and open(path, "rb").read(8) == b"\x89PNG\r\n\x1a\n"
    assert problems == []
    page.goto((dist / "index.html").resolve().as_uri() + "?embed=1#y2014-vn")
    page.wait_for_timeout(1000)
    assert page.locator(".site-head").is_hidden() and page.locator("#amap-explore").is_hidden()
    assert page.locator("#amap-embed-credit").is_visible() and page.locator("#curtain").is_hidden()
    page.close()


def test_whats_new_and_its_feed(tmp_path):
    """Ticket 40: the project's added moves, corrections and retractions, newest first, as a page and an
    Atom feed with absolute links; Chubb's own moves are not news. Built from the full data (the MATS-only
    copy the other site tests use holds no project moves)."""
    from xml.dom import minidom
    from web.build import SITE_URL, build as build_site
    from tests.conftest import DATA_DIR as FULL
    out = tmp_path / "site"
    build_site(FULL, out, build_date="2026-11-23")
    page = (out / "whats-new.html").read_text(encoding="utf-8")
    project = [m for m in read_csv(FULL / "moves.csv") if m["coded_by"] != "chubb" and m["status"] == "accepted"]
    assert project and all(f'href="cases/{m["move_id"]}.html"' in page for m in project)
    assert "CN201702" in page and "Retracted" in page                      # the retraction, without a page link
    assert 'href="cases/CN201702.html"' not in page
    doc = minidom.parse(str(out / "feed.xml"))
    entries = doc.getElementsByTagName("entry")
    assert 0 < entries.length <= 50
    links = [e.getElementsByTagName("link")[0].getAttribute("href") for e in entries]
    assert all(h.startswith(SITE_URL) for h in links)
    assert 'type="application/atom+xml"' in (out / "index.html").read_text(encoding="utf-8")
