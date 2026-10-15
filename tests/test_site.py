"""Seam 3: the site build. Aggregates equal the validator's; pages render without errors; bundle is portable."""
import json
import re
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
    for page in ("index.html", "methodology.html"):
        html = (dist / page).read_text(encoding="utf-8")
        # every src/href that is not an external link is relative (no leading slash, no absolute file path)
        for attr, target in re.findall(r'(src|href)="([^"]+)"', html):
            assert not target.startswith("/"), (page, target)
            if not target.startswith(("http://", "https://", "#", "mailto:")):
                assert (dist / target.split("#")[0]).exists(), (page, target)
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
