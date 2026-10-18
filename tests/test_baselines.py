"""Each claimant has a pre-1970 baseline document: the actions against which its 1970 level is
measured (Chubb's rule). Chubb's PRC list is reproduced; the five others are the project's, sourced."""
import csv
import re
from pathlib import Path

from tests.conftest import DATA_DIR

BASELINES = DATA_DIR / "baselines"


def claimants():
    with open(DATA_DIR / "claimants.csv", newline="", encoding="utf-8") as f:
        return [r["code"] for r in csv.DictReader(f)]


def test_every_claimant_has_a_baseline_document():
    for code in claimants():
        p = BASELINES / f"{code}.md"
        assert p.exists(), p
        text = p.read_text(encoding="utf-8")
        assert text.startswith("# "), code
        rows = [l for l in text.splitlines() if l.startswith("| ") and not l.startswith("| Date") and not l.startswith("| Period") and not set(l) <= set("|- ")]
        assert len(rows) >= 5, (code, len(rows))


def test_chubbs_prc_list_is_reproduced_from_the_appendix():
    text = (BASELINES / "CN.md").read_text(encoding="utf-8")
    appendix = re.sub(r"[\s|]+", " ", (Path(__file__).resolve().parents[1] / "docs/codebook/chubb-2021-appendix.txt").read_text(encoding="utf-8"))
    assert "doi:10.7910/DVN/3Y7NRU" in text and "CC0" in text
    for phrase in ("First PRC map published incorporating ROC eleven-dash line", "Office for Zhongsha, Xisha and Nansha Affairs established",
                   "497 protests and warnings"):
        assert phrase in text and phrase in appendix


def test_project_baselines_cite_a_source_per_row():
    """Every row of the five project-compiled lists carries a URL; every document names its sources."""
    for code in ("VN", "PH", "MY", "ID", "TW"):
        text = (BASELINES / f"{code}.md").read_text(encoding="utf-8")
        assert "## Sources consulted" in text, code
        header = next(l for l in text.splitlines() if l.startswith("| Date"))
        cols = [c.strip() for c in header.strip("|").split("|")]
        assert "Source (URL)" in cols and "Quote" in cols, (code, cols)
        src_i = cols.index("Source (URL)")
        rows = [l for l in text.splitlines() if l.startswith("| ") and l is not header and not set(l) <= set("|- ")]
        rows = [r for r in rows if r.split("|")[1].strip() != "Date"]
        for r in rows:
            cells = [c.strip() for c in r.strip("|").split("|")]
            if len(cells) != len(cols):
                continue
            assert re.search(r"https?://", cells[src_i]), (code, r[:80])
