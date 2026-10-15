"""Seam 3: the site build. Aggregates equal the validator's; pages render without errors; bundle is portable."""
import json
import re
from html import escape as html_escape
from pathlib import Path

import pytest

from pipeline.validate import aggregates
from tests.conftest import DATA_DIR
from web.build import build, read_csv


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
    for page in ("index.html", "methodology.html", "cases.html", "cases/VN197301.html", "cases/CN201105.html"):
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


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _open(browser, dist, page_name, viewport=(1280, 900), color_scheme="light"):
    ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, color_scheme=color_scheme)
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(("console", m.type, m.text)) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(("pageerror", str(e))))
    page.on("requestfailed", lambda r: problems.append(("requestfailed", r.url)))
    page.goto((dist / page_name).resolve().as_uri())
    page.wait_for_timeout(300)
    page.on("close", lambda _: ctx.close())
    return page, problems


@pytest.mark.parametrize("page_name", ["index.html", "methodology.html", "issues-domains.html", "subregions.html", "cases.html"])
@pytest.mark.parametrize("viewport,scheme", [((1280, 900), "light"), ((390, 800), "light"), ((1280, 900), "dark")])
def test_pages_render_without_errors(browser, dist, page_name, viewport, scheme):
    page, problems = _open(browser, dist, page_name, viewport, scheme)
    assert problems == []
    assert page.title()
    assert not page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "horizontal page scroll"
    if page_name == "index.html":
        # the main chart fits the viewport at phone width (no internal scroll hiding recent years)
        assert page.locator('[data-chart="all-claimants"].is-scrollable').count() == 0
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
    # filter: drop China and the legend and note follow
    page.locator('.chip[data-code="CN"] input').uncheck(force=True)
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
    page.locator('.chip[data-code="CN"] input').check(force=True)
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
    """The map page with the basemap tiles answered locally: the test is offline except for that stub."""
    ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, color_scheme=color_scheme)
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(("console", m.type, m.text)) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(("pageerror", str(e))))
    page.on("requestfailed", lambda r: problems.append(("requestfailed", r.url)))
    tiles = []
    def stub(route):
        tiles.append(route.request.url)
        route.fulfill(status=200, content_type="image/png", body=PNG_1x1)
    page.route("https://tile.openstreetmap.org/**", stub)
    page.goto((dist / "map.html").resolve().as_uri())
    page.wait_for_timeout(600)
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
    assert page.locator(".sr-poly").count() == 10
    assert page.locator(".leaflet-tile-loaded").count() > 0 and tiles, "basemap tiles requested from the attribution-compliant provider"
    text = page.inner_text("#map-count")
    assert text.startswith(f"{expected['n_events']} events") and f"{expected['n_points']} placed" in text
    # the sub-region counts on the map are the validator's, summed over claimants
    shown = {}
    for el in page.locator(".leaflet-marker-icon").element_handles():
        title = el.get_attribute("title") or ""
        mm = re.search(r"^(\d+) events? known only to sub-region (\d+)", title)
        if mm:
            shown[mm.group(2)] = int(mm.group(1))
    want = {}
    for c in expected["by_claimant"].values():
        for sr, n in c["subregions"].items():
            if n:
                want[sr] = want.get(sr, 0) + n
    assert shown == want
    assert page.locator(".leaflet-marker-icon").count() == len(want) + len({(e.get("lat"), e.get("lon")) for e in json.loads((dist / "data/events.json").read_text(encoding="utf-8"))["events"] if "lat" in e})
    assert not problems, problems


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
