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
    for key in ("years", "types", "claimants", "n_moves", "n_pending", "by_claimant"):
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


@pytest.mark.parametrize("page_name", ["index.html", "methodology.html"])
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
