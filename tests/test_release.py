"""Releases (ticket 09): the files served come from the tag, not the working tree; checksums and the
zip are reproducible; the Downloads page says which version it serves; the root citation and the
changelog agree with the dataset version."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from pipeline import release, schema
from tests.conftest import DATA_DIR, ROOT
from web.build import build


@pytest.fixture
def tagged_repo(tmp_path, monkeypatch):
    """A git repository holding a copy of data/ with one tag, then one more commit that changes moves.csv."""
    for k, v in dict(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                     GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com", GIT_COMMITTER_DATE="2026-10-15T12:00:00+00:00",
                     GIT_AUTHOR_DATE="2026-10-15T12:00:00+00:00").items():
        monkeypatch.setenv(k, v)
    repo = tmp_path / "repo"
    shutil.copytree(DATA_DIR, repo / "data", ignore=shutil.ignore_patterns("raw"))
    shutil.copy(ROOT / "CHANGELOG.md", repo / "CHANGELOG.md")
    def git(*a):
        subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("add", "."); git("commit", "-q", "-m", "data")
    git("tag", "-a", "v2.0.0-dev", "-m", "Dataset v2.0.0-dev")
    import csv
    moves = repo / "data/moves.csv"
    rows = list(csv.DictReader(open(moves, newline="", encoding="utf-8")))
    rows[0]["description"] += " [changed after the tag]"
    with open(moves, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    git("commit", "-qam", "after the tag")
    return repo


def test_assets_come_from_the_tag_not_the_working_tree(tagged_repo, tmp_path):
    assert release.latest_tag(tagged_repo) == "v2.0.0-dev"
    out = tmp_path / "assets"
    m = release.build_assets(tagged_repo, "v2.0.0-dev", out)
    assert m["tag"] == "v2.0.0-dev" and m["version"] == "2.0.0-dev" and m["date"].startswith("2026-10-15")
    assert (out / "moves.csv").read_bytes() == (DATA_DIR / "moves.csv").read_bytes()            # the tag's content
    assert b"changed after the tag" not in (out / "moves.csv").read_bytes()
    names = {f["name"] for f in m["files"]}
    assert names == {Path(p).name for p in release.RELEASE_FILES} | {"CITATION.cff", "README.txt", "SHA256SUMS"}
    # checksums are right and the SHA256SUMS file verifies every other file
    for f in m["files"]:
        assert hashlib.sha256((out / f["name"]).read_bytes()).hexdigest() == f["sha256"] and (out / f["name"]).stat().st_size == f["bytes"]
    sums = dict(line.split("  ", 1)[::-1] for line in (out / "SHA256SUMS").read_text().splitlines())
    assert set(sums) == names - {"SHA256SUMS"}
    assert all(hashlib.sha256((out / n).read_bytes()).hexdigest() == h for n, h in sums.items())
    # the zip holds the same files under a versioned folder and is reproducible
    with zipfile.ZipFile(out / m["zip"]["name"]) as z:
        assert sorted(z.namelist()) == sorted(f"scs-developments-tracker-v2.0.0-dev/{n}" for n in names)
        assert z.read("scs-developments-tracker-v2.0.0-dev/moves.csv") == (out / "moves.csv").read_bytes()
        assert {i.date_time for i in z.infolist()} == {(2026, 10, 15, 12, 0, 0)}
    again = release.build_assets(tagged_repo, "v2.0.0-dev", tmp_path / "again")
    assert again["zip"]["sha256"] == m["zip"]["sha256"]
    # the citation inside carries the version and the tag date
    cff = (out / "CITATION.cff").read_text(encoding="utf-8")
    assert 'version: "2.0.0-dev"' in cff and 'date-released: "2026-10-15"' in cff and "Chubb" in cff


def test_no_tag_means_no_release(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    repo = tmp_path / "bare"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    assert release.latest_tag(repo) is None
    assert release.latest_tag(tmp_path / "not-a-repo") is None
    with pytest.raises(RuntimeError):
        release.tag_date(repo, "v9.9.9")


@pytest.mark.parametrize("tag, ok", [("v2.0.0-dev", True), ("v2.1.0", True), ("v2.0.0-rc.1", True), ("2.0.0", False), ("v2.0", False), ("latest", False)])
def test_tag_shape(tag, ok):
    assert bool(release.TAG_RE.match(tag)) == ok


def test_changelog_section_and_root_citation_match_the_dataset_version():
    v = schema.DATASET_VERSION
    notes = release.changelog_section(f"v{v}")
    assert notes and "MATS 1.02" in notes
    assert release.changelog_section("v0.0.0") == ""
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert f'version: "{v}"' in cff and re.search(r'date-released: "\d{4}-\d{2}-\d{2}"', cff)
    assert "pyproject" not in cff
    # the package version agrees too (PEP 440 spelling of the same number)
    assert v.replace("-dev", ".dev0") in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_cli(tagged_repo, tmp_path, monkeypatch):
    monkeypatch.setattr(release, "ROOT", tagged_repo)
    monkeypatch.setattr(release, "CHANGELOG", tagged_repo / "CHANGELOG.md")
    assert release.main(["assets", "--out", str(tmp_path / "a")]) == 0 and (tmp_path / "a/SHA256SUMS").exists()
    assert release.main(["notes"]) == 0
    assert release.main(["assets", "--out", str(tmp_path / "b"), "--tag", "nope"]) == 1
    assert release.main(["latest"]) == 0


def test_site_serves_the_tagged_files_and_says_so(tagged_repo, tmp_path):
    out = tmp_path / "dist"
    build(tagged_repo / "data", out, build_date="2026-10-16", repo=tagged_repo)
    html = (out / "downloads.html").read_text(encoding="utf-8")
    m = json.loads((out / "downloads/manifest.json").read_text(encoding="utf-8"))
    assert m["tag"] == "v2.0.0-dev"
    assert "tagged <code>v2.0.0-dev</code> on 2026-10-15" in html and "unreleased working copy" not in html
    assert "still being built" in html                                   # the -dev suffix is explained
    for f in m["files"]:
        assert f'href="downloads/{f["name"]}"' in html and f["sha256"] in html
    assert f'href="downloads/{m["zip"]["name"]}"' in html and m["zip"]["sha256"] in html
    assert (out / "downloads" / m["zip"]["name"]).exists()
    assert b"changed after the tag" not in (out / "downloads/moves.csv").read_bytes()
    assert "What changed in v2.0.0-dev" in html and "<li>" in html
    assert "Dataset version 2.0.0-dev (released 2026-10-15)" in html and "@dataset{" in html and "Chubb, A. (2021)" in html
    assert 'href="downloads.html#cite"' in (out / "methodology.html").read_text(encoding="utf-8")


def test_site_without_a_tag_serves_the_working_copy_labelled(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    repo = tmp_path / "repo"
    shutil.copytree(DATA_DIR, repo / "data", ignore=shutil.ignore_patterns("raw"))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    out = tmp_path / "dist"
    build(repo / "data", out, build_date="2026-10-16", repo=repo)
    html = (out / "downloads.html").read_text(encoding="utf-8")
    assert "unreleased working copy" in html and "scs-developments-tracker-unreleased.zip" in html
    assert (out / "downloads/moves.csv").read_bytes() == (DATA_DIR / "moves.csv").read_bytes()
    assert "accessed 2026-10-16" in html
