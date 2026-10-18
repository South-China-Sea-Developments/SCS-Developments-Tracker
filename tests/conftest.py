from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW_XLSX = ROOT / "data/raw/mats-1.02/MATS_1-02_all_cases.xlsx"
RAW_MAVD = ROOT / "data/raw/mavd-arcgis-2023/All_Actions7.csv"
DATA_DIR = ROOT / "data"


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
