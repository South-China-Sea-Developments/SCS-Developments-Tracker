"""Seam 3: the site build. Aggregates equal the validator's; pages render without errors; bundle is portable."""
import json
import re
from html import escape as html_escape
from pathlib import Path

import pytest

from pipeline.validate import aggregates
from tests.conftest import DATA_DIR
from web.build import build, read_csv


EMPTY_TILEJSON = json.dumps({"tilejson": "3.0.0", "tiles": ["https://tiles.openfreemap.org/stub/{z}/{x}/{y}.pbf"], "minzoom": 0, "maxzoom": 14, "vector_layers": []})
HEADLESS_NOISE = re.compile(r"WebGL|swiftshader|GL Driver|GPU stall", re.I)


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    build(DATA_DIR, out, build_date="2026-01-01")
    return out


def test_aggregates_match_validator(dist):
    built = json.loads((dist / "data/aggregates.json").read_text(encoding="utf-8"))
    independent = aggregates(read_csv(DATA_DIR / "moves.csv"))
    for key in ("years", "types", "domains", "issues", "subregions", "claimants", "n_moves", "n_pending", "by_claimant"):
        assert built[key] == independent[key], key
    # the inline copy the page uses is the same data
    inline = re.search(r'<script id="agg" type="application/json">(.*?)</script>', (dist / "index.html").read_text(encoding="utf-8"), re.S)
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


def _open(browser, dist, page_name, viewport=(1280, 900), color_scheme="light"):
    """Any page, offline: the basemap host is answered by the same stubs as on the map page, since
    the home page carries the map too."""
    ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, color_scheme=color_scheme)
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(("console", m.type, m.text)) if m.type in ("error", "warning") and not HEADLESS_NOISE.search(m.text) else None)
    page.on("pageerror", lambda e: problems.append(("pageerror", str(e))))
    page.on("requestfailed", lambda r: problems.append(("requestfailed", r.url)))
    page.route("https://tiles.openfreemap.org/**", _tile_stub([]))
    page.goto((dist / page_name).resolve().as_uri())
    page.wait_for_timeout(300 if page_name != "index.html" else 1200)
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


@pytest.mark.parametrize("page_name", ["index.html", "methodology.html", "issues-domains.html", "subregions.html", "cases.html", "downloads.html"])
@pytest.mark.parametrize("viewport,scheme", [((1280, 900), "light"), ((1024, 768), "light"), ((390, 800), "light"), ((1280, 900), "dark")])
def test_pages_render_without_errors(browser, dist, page_name, viewport, scheme):
    page, problems = _open(browser, dist, page_name, viewport, scheme)
    assert problems == []
    assert page.title()
    assert not page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "horizontal page scroll"
    if page_name == "index.html":
        # the main chart fits the viewport at phone width (no internal scroll hiding recent years)
        assert page.locator('[data-chart="all-claimants"].is-scrollable').count() == 0
    page.close()


def test_home_leads_with_numbers_map_and_latest_developments(browser, dist):
    """Ticket 15: the first viewport carries the lede, three headline numbers from the aggregates and the
    event map; the latest-developments list is the newest accepted events in the files, newest first."""
    agg = aggregates(read_csv(DATA_DIR / "moves.csv"))
    page, problems = _open(browser, dist, "index.html")
    assert problems == []
    nums = {el.get_attribute("data-stat"): el.inner_text().replace(",", "") for el in page.locator(".stat [data-stat]").element_handles()}
    assert nums["moves"] == str(agg["n_moves"])
    claimants_coded = sum(1 for c, v in agg["by_claimant"].items() if sum(y["total"] for y in v["years"].values()))
    assert nums["claimants"] == str(claimants_coded)
    assert nums["years"] == f"{agg['years'][0]}–{agg['years'][-1]}"
    # the map is on the home page and draws offline, and takes most of the first viewport (the maintainer's
    # ask): at least half of the viewport height is map canvas, at a tall and at a short desktop window
    assert page.locator("#map canvas.maplibregl-canvas").count() == 1 and page.locator(".sr-label").count() == 10
    for vh, share in ((900, 0.5), (720, 0.4)):   # a short laptop window keeps the lede and numbers, so the map gets a little less
        page.set_viewport_size({"width": 1280, "height": vh})
        page.wait_for_timeout(200)
        visible = page.evaluate("(vh) => { const r = document.getElementById('map').getBoundingClientRect(); return Math.min(r.bottom, vh) - Math.max(r.top, 0); }", vh)
        assert visible >= share * vh, f"{visible}px of map visible in a {vh}px viewport"
    page.set_viewport_size({"width": 1280, "height": 900})
    # latest developments: the newest accepted events of accepted moves, newest first, one row per move,
    # MATS-era seed dates outside their move's year (known MAVD typos) left out, each linking to its move
    moves = {m["move_id"]: m for m in read_csv(DATA_DIR / "moves.csv")}
    events = [e for e in read_csv(DATA_DIR / "events.csv") if e["status"] == "accepted" and e["date_start"]
              and moves[e["move_id"]]["status"] == "accepted" and (e["extractor"] or e["date_start"][:4] == moves[e["move_id"]]["year"])]
    events.sort(key=lambda e: (e["date_start"], e["event_id"]), reverse=True)
    expected, seen = [], set()
    for e in events:
        if e["move_id"] not in seen:
            seen.add(e["move_id"]); expected.append(e)
    rows = page.locator("#latest .latest-row")
    assert rows.count() == min(8, len(expected))
    for i in range(rows.count()):
        row = rows.nth(i)
        assert row.get_attribute("data-event") == expected[i]["event_id"]
        assert row.locator("a[href^='cases/']").first.get_attribute("href") == f"cases/{expected[i]['move_id']}.html"
        dt_attr = row.locator("time").get_attribute("datetime")
        assert dt_attr == {"year": expected[i]["date_start"][:4], "month": expected[i]["date_start"][:7]}.get(expected[i]["date_precision"], expected[i]["date_start"])
    page.close()


@pytest.mark.parametrize("viewport,scheme", [((390, 800), "light"), ((1280, 900), "dark")])
def test_home_map_draws_at_phone_width_and_in_dark_mode(browser, dist, viewport, scheme):
    page, problems = _open(browser, dist, "index.html", viewport, scheme)
    assert problems == []
    assert page.locator("#map canvas.maplibregl-canvas").count() == 1 and page.locator(".sr-label").count() == 10
    page.close()


def _luma(css_rgb):
    """Gamma-encoded luma of a CSS rgb() string, enough to tell a dark plane from a light one."""
    r, g, b = [int(x) for x in re.findall(r"\d+", css_rgb)[:3]]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_visual_identity_follows_the_references(browser, dist):
    """Ticket 16: the home page opens on a dark sea band with the title in the light display face in
    white over it and a short rule under it, drawn (an inline SVG), not photographed; the map sits in a
    dark panel with light labels; inner pages are white article pages with a kicker over the title;
    the display face is the vendored geometric sans; and no page or asset carries the institution's
    name or mark (its visual language is adopted; its identity is not)."""
    page, problems = _open(browser, dist, "index.html")
    assert problems == []
    assert page.evaluate("[...document.fonts].some(f => f.family === 'Outfit' && f.status === 'loaded')"), "the display face is Outfit, loaded from the bundle"
    title_rgb, band_rgb = page.evaluate("[getComputedStyle(document.querySelector('.hero h1')).color, getComputedStyle(document.querySelector('.sea')).backgroundColor]")
    assert _luma(title_rgb) > 230 and _luma(band_rgb) < 60, (title_rgb, band_rgb)
    assert "Outfit" in page.evaluate("getComputedStyle(document.querySelector('.hero h1')).fontFamily")
    assert int(page.evaluate("getComputedStyle(document.querySelector('.hero h1')).fontWeight")) <= 400, "light, as in the banner"
    rule = page.evaluate("(() => { const s = getComputedStyle(document.querySelector('.hero h1'), '::after'); return [s.content, parseFloat(s.width), s.backgroundColor]; })()")
    assert rule[0] != "none" and 40 <= rule[1] <= 160 and _luma(rule[2]) > 200, rule
    assert page.locator(".sea > svg.sea-art").count() == 1 and page.locator(".sea img").count() == 0
    assert "url(" not in page.evaluate("getComputedStyle(document.querySelector('.sea')).backgroundImage")
    panel_rgb, chip_rgb = page.evaluate("[getComputedStyle(document.querySelector('.map-section')).backgroundColor, getComputedStyle(document.querySelector('#map-claimant-filter .chip span:last-child')).color]")
    assert _luma(panel_rgb) < 60 and _luma(chip_rgb) > 180, (panel_rgb, chip_rgb)
    page.close()
    page, problems = _open(browser, dist, "methodology.html")
    assert problems == []
    assert _luma(page.evaluate("getComputedStyle(document.body).backgroundColor")) > 250, "white article paper"
    kicker = page.locator("main .kicker").first
    assert page.evaluate("(k) => [getComputedStyle(k).textTransform, parseFloat(getComputedStyle(k).letterSpacing) > 0.5]", kicker.element_handle()) == ["uppercase", True]
    assert page.evaluate("document.querySelector('main .kicker').compareDocumentPosition(document.querySelector('main h1')) & Node.DOCUMENT_POSITION_FOLLOWING"), "the kicker precedes the title"
    page.close()
    # the site's chrome — templates, styles, scripts, assets — carries no institution's name or mark; the data
    # pages (cases, their index, the latest list) and the project documents under downloads/ are data and may
    forbidden = re.compile(r"asia\s*society|\bASPI\b|leogryph|asiasociety", re.I)
    chrome = [p for d in (Path("web/templates"), Path("web/static"), dist / "assets") for p in d.rglob("*") if p.is_file() and p.suffix in (".html", ".css", ".js", ".svg", ".json", ".txt")]
    assert len(chrome) > 10
    for path in chrome:
        assert not forbidden.search(path.read_text(encoding="utf-8", errors="ignore")), path
    assert not [p for p in (dist / "assets").rglob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif")], "no photographs in the bundle"


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
        if page.evaluate("document.activeElement && document.activeElement.textContent") == "Data and code":
            break
    assert page.evaluate("document.activeElement.textContent") == "Data and code"
    box = page.evaluate("(() => { const r = document.activeElement.getBoundingClientRect(); return [r.left, r.right]; })()")
    assert 0 <= box[0] and box[1] <= 390, box
    # at a tablet width the nav has moved under the brand rather than hiding links behind the brand
    page.set_viewport_size({"width": 1024, "height": 800})
    page.wait_for_timeout(100)
    assert page.evaluate(f"{nav}.getBoundingClientRect().top") > page.evaluate("document.querySelector('.brand').getBoundingClientRect().bottom") - 1
    page.close()


def test_overview_charts_and_controls(browser, dist):
    page, problems = _open(browser, dist, "index.html")
    # one stacked chart for all claimants plus one per claimant with data
    assert page.locator('[data-chart="all-claimants"] svg').count() == 1
    assert page.locator('[data-chart="by-type"] svg').count() == 3
    assert page.locator('[data-chart="by-type"] .empty').count() == 3
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
    assert "213 moves across 5 of 6 claimants" in page.locator("#filters-note").inner_text()
    assert page.locator("#fig-CN").is_hidden()
    assert page.locator('#fig-all .legend .key').count() == 5
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
    moves = _moves()
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
    pending = (dist / "cases/VN197304.html").read_text(encoding="utf-8")
    assert "awaits the author" in pending and "not counted" in pending


def test_case_index_matches_the_files(dist):
    page = (dist / "cases.html").read_text(encoding="utf-8")
    inline = re.search(r'<script id="cases" type="application/json">(.*?)</script>', page, re.S)
    index = json.loads(inline.group(1))["cases"]
    moves = {m["move_id"]: m for m in _moves()}
    assert {c["id"] for c in index} == set(moves)
    c = next(c for c in index if c["id"] == "CN197401")
    assert c["t"] == ["force"] and 2 in c["s"] and "V" in c["g"] and c["y"] == 1974


def test_case_browser_filters(browser, dist):
    page, problems = _open(browser, dist, "cases.html")
    moves = _moves()
    n_all = len(moves)
    n_acc = sum(1 for m in moves if m["status"] == "accepted")
    assert page.locator("#count").inner_text() == f"{n_acc} moves and {n_all - n_acc} pending"
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


@pytest.mark.parametrize("move_id", ["CN197001", "CN197401", "PH199501", "VN201104", "VN197304", "CN201504", "PH201404"])
def test_case_pages_render_without_errors(browser, dist, move_id):
    page, problems = _open(browser, dist, f"cases/{move_id}.html", viewport=(390, 800))
    assert problems == []
    assert page.locator(".inset svg path").count() == 10
    assert not page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    page.close()


# ---- ticket 04: issues/domains and sub-regions pages -----------------------

def _count(moves, **flags):
    return sum(1 for m in moves if all(m[k] == v for k, v in flags.items()))


def test_issues_and_domains_pages_match_the_files(browser, dist):
    page, problems = _open(browser, dist, "issues-domains.html")
    moves = [m for m in _moves() if m["status"] == "accepted"]
    # issues by year (all claimants): 1988 energy mentions
    page.locator('[data-toggle-table="fig-issues-all"]').click()
    page.wait_for_timeout(100)
    row = page.locator("#fig-issues-all .table-view tbody tr", has_text="1988").first.inner_text().split("\t")
    header = page.locator("#fig-issues-all .table-view thead th").all_inner_texts()
    assert row[header.index("Energy")] == str(_count(moves, year="1988", energy="1"))
    assert row[header.index("Military")] == str(_count(moves, year="1988", military="1"))
    # issues by sub-region: Paracels x Fisheries, all claimants
    page.locator('[data-toggle-table="fig-issues-loc"]').click()
    page.wait_for_timeout(100)
    row = page.locator("#fig-issues-loc .table-view tbody tr", has_text="2 Paracels").first.inner_text().split("\t")
    header = page.locator("#fig-issues-loc .table-view thead th").all_inner_texts()
    assert row[header.index("Fisheries")] == str(_count(moves, loc02_paracels="1", fisheries="1"))
    # domains per claimant: Vietnam, diplomatic, 1994
    page.locator('[data-toggle-table="fig-domains-VN"]').click()
    page.wait_for_timeout(100)
    row = page.locator("#fig-domains-VN .table-view tbody tr", has_text="1994").first.inner_text().split("\t")
    header = page.locator("#fig-domains-VN .table-view thead th").all_inner_texts()
    assert row[header.index("Diplomatic")] == str(_count(moves, claimant="VN", year="1994", diplomatic="1"))
    # the filter row scopes everything: drop China and the all-claimants chart's China share disappears
    page.locator('.chip[data-code="CN"] input').uncheck(force=True)
    page.wait_for_timeout(100)
    row = page.locator("#fig-issues-all .table-view tbody tr", has_text="1988").first.inner_text().split("\t")
    header = page.locator("#fig-issues-all .table-view thead th").all_inner_texts()
    assert row[header.index("Military")] == str(sum(1 for m in moves if m["year"] == "1988" and m["military"] == "1" and m["claimant"] != "CN"))
    assert problems == []
    page.close()


def test_subregions_page_map_and_bins(browser, dist):
    page, problems = _open(browser, dist, "subregions.html")
    moves = [m for m in _moves() if m["status"] == "accepted"]
    assert page.locator(".choropleth .zone").count() == 10
    assert page.locator('[data-chart="years"][data-dim="subregion"] svg').count() == 10
    bins = page.locator("#map-bin label span").all_inner_texts()
    assert bins[:3] == ["All years", "1970", "1971–75"] and bins[-1] == "2011–15"
    # the small multiples use one colour per selection, never China's on every claimant
    page.locator('#map-claimant input[value="VN"]').check(force=True)
    page.wait_for_timeout(150)
    fill = page.locator('[data-chart="years"][data-dim="subregion"] .seg').first.get_attribute("fill")
    assert fill.lower() == page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--vn').trim()").lower()
    page.locator('#map-claimant input[value="ALL"]').check(force=True)
    page.wait_for_timeout(150)
    # fills change with the period
    fills = lambda: [z.get_attribute("fill") for z in page.locator(".choropleth .zone").all()]
    before = fills()
    page.locator('#map-bin input[value="2011-2015"]').check(force=True)
    page.wait_for_timeout(150)
    after = fills()
    assert before != after
    # the table twin holds the period counts: Paracels (2), 2011-15, all claimants
    page.locator('[data-toggle-table="fig-map"]').click()
    page.wait_for_timeout(100)
    header = page.locator("#fig-map .table-view thead th").all_inner_texts()
    row = page.locator("#fig-map .table-view tbody tr", has_text="2011–15").first.inner_text().split("\t")
    expect = sum(1 for m in moves if m["loc02_paracels"] == "1" and 2011 <= int(m["year"]) <= 2015)
    assert row[header.index("2 Paracels")] == str(expect)
    # claimant selector scopes the map, the type chart and the small multiples
    page.locator('#map-claimant input[value="PH"]').check(force=True)
    page.wait_for_timeout(150)
    row = page.locator("#fig-map .table-view tbody tr", has_text="2011–15").first.inner_text().split("\t")
    expect = sum(1 for m in moves if m["claimant"] == "PH" and m["loc02_paracels"] == "1" and 2011 <= int(m["year"]) <= 2015)
    assert row[header.index("2 Paracels")] == str(expect)
    page.locator('[data-toggle-table="fig-loc-type"]').click()
    page.wait_for_timeout(100)
    header = page.locator("#fig-loc-type .table-view thead th").all_inner_texts()
    row = page.locator("#fig-loc-type .table-view tbody tr", has_text="6 Spratly NE").first.inner_text().split("\t")
    assert row[header.index("Total")] == str(sum(1 for m in moves if m["claimant"] == "PH" and m["loc06_spratly_ne"] == "1"))
    # hovering a zone shows its counts
    page.locator('[data-toggle-table="fig-map"]').click()
    page.hover(".choropleth .zone >> nth=5")
    page.wait_for_timeout(50)
    assert "Spratly NE" in page.locator(".tooltip").inner_text()
    assert problems == []
    page.close()


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




def _open_map(browser, dist, viewport=(1280, 900), color_scheme="light"):
    """The map page with the basemap answered locally: the TileJSON names a stub tile URL that
    returns no content, as do fonts and sprites. The test is offline except for those stubs."""
    ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, color_scheme=color_scheme)
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(("console", m.type, m.text)) if m.type in ("error", "warning") and not HEADLESS_NOISE.search(m.text) else None)
    page.on("pageerror", lambda e: problems.append(("pageerror", str(e))))
    page.on("requestfailed", lambda r: problems.append(("requestfailed", r.url)))
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
        assert ("lat" in e) != ("sr" in e)
        if "sr" in e:
            assert e["sr"] and all(s in {str(i) for i in range(1, 11)} for s in e["sr"])
    assert [f["properties"]["n"] for f in data["subregions"]["features"]] == list(range(1, 11))


@pytest.mark.parametrize("viewport,scheme", [((1280, 900), "light"), ((390, 800), "light"), ((1280, 900), "dark")])
def test_map_renders_offline_without_errors(browser, dist, viewport, scheme):
    from pipeline.validate import event_aggregates
    page, problems, tiles = _open_map(browser, dist, viewport, scheme)
    expected = event_aggregates(read_csv(DATA_DIR / "events.csv"), read_csv(DATA_DIR / "moves.csv"))
    assert page.locator("canvas.maplibregl-canvas").count() == 1 and page.locator(".sr-label").count() == 10
    assert any(t.rstrip("/").endswith("/planet") for t in tiles), "basemap requested from the attribution-compliant provider"
    assert "OpenFreeMap" in page.inner_text(".maplibregl-ctrl-attrib") and "OpenStreetMap" in page.inner_text(".maplibregl-ctrl-attrib")
    text = page.inner_text("#map-count")
    assert text.startswith(f"{expected['n_events']} events") and f"{expected['n_points']} placed" in text
    # the sub-region counts on the map are the validator's, summed over claimants
    shown = {}
    for el in page.locator("[role='button'][tabindex='0']").element_handles():
        title = el.get_attribute("title") or ""
        mm = re.search(r"^(\d+) events? in sub-region (\d+) .* without a point$", title)
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
    unplaced) so the point-marker code is exercised while the real data has no coordinates yet."""
    import csv
    import shutil
    d = tmp_path_factory.mktemp("placed") / "data"
    shutil.copytree(DATA_DIR, d, ignore=shutil.ignore_patterns("raw"))
    rows = list(csv.DictReader(open(d / "events.csv", newline="", encoding="utf-8")))
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
    assert "3 placed" in page.inner_text("#map-count")
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
        text = page.inner_text("#map-count")
        return int(re.search(r"(\d+) placed", text).group(1)), int(re.search(r"(\d+) by sub-region", text).group(1))
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
    assert page.inner_text("#map-count").startswith(f"{len(in_2014)} events Jan 2014 – Dec 2014")
    # unchecking a claimant removes its events; a type filter keeps only moves of that type
    page.uncheck('input[name="claimant"][value="VN"]')
    page.wait_for_timeout(300)
    assert page.inner_text("#map-count").startswith(f"{len([e for e in in_2014 if e['claimant'] != 'VN'])} events")
    page.click("#reset")
    page.check('input[name="t"][value="coercive"]')
    page.wait_for_timeout(300)
    coercive = [e for e in shown if moves[e["move_id"]]["coercive"] == "1"]
    assert page.inner_text("#map-count").startswith(f"{len(coercive)} events through")
    # the list twin names every event in view with a link to its move
    page.click("#list-toggle")
    page.wait_for_timeout(300)
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
    agg_html = (out / "index.html").read_text(encoding="utf-8")
    inline = json.loads(re.search(r'<script id="agg"[^>]*>(.*?)</script>', agg_html, re.S).group(1).replace("<\\/", "</"))
    assert inline["by_claimant"]["MY"]["years"]["2021"]["coercive"] == 1 and inline["years"][-1] == 2021
