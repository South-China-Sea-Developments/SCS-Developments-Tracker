from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW_XLSX = ROOT / "data/raw/mats-1.02/MATS_1-02_all_cases.xlsx"
RAW_MAVD = ROOT / "data/raw/mavd-arcgis-2023/All_Actions7.csv"
DATA_DIR = ROOT / "data"


@pytest.fixture(scope="session")
def mats_data(tmp_path_factory):
    """A copy of data/ holding only what the loader made from MATS 1.02 and the MAVD table: Chubb's moves,
    the seed events and their sources. The project's own decisions (moves coded_by=project, harvested
    events and their sources) are stripped, so tests of the loader and the site against Chubb's known
    counts keep passing as the dataset grows. Corrections stay: they document the chubb rows as they are."""
    import csv
    import shutil

    d = tmp_path_factory.mktemp("mats") / "data"
    shutil.copytree(DATA_DIR, d, ignore=shutil.ignore_patterns("raw"))

    def filter_csv(name, keep):
        with open(d / f"{name}.csv", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            fields, rows = r.fieldnames, [x for x in r if keep(x)]
        with open(d / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        return rows

    filter_csv("moves", lambda m: m["coded_by"] == "chubb")
    kept = {e["event_id"] for e in filter_csv("events", lambda e: e["harvest_run_id"].startswith("seed"))}
    filter_csv("sources", lambda s_: s_["event_id"] in kept)
    return d


@pytest.fixture(scope="session")
def loaded():
    """Canonical tables built in memory from the raw inputs (never touches data/*.csv)."""
    from pipeline.load_mats import load_tables

    return load_tables(RAW_XLSX, RAW_MAVD)


@pytest.fixture(scope="session")
def raw_xlsx_rows():
    import openpyxl

    wb = openpyxl.load_workbook(RAW_XLSX, read_only=True)
    rows = list(wb["MATS 1.02 cases"].iter_rows(values_only=True))  # sheet name fixed by the raw file
    header = rows[0]
    return [dict(zip(header, r)) for r in rows[1:] if r[2]]


@pytest.fixture(scope="module")
def browser():
    """One headless Chromium per test module, for the seam-3 render tests."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()
