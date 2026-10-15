"""Releases: the dataset at a tag, as downloadable files with checksums and a citation.

A release is a git tag `vX.Y.Z` (or `vX.Y.Z-dev`) on `main`. This module reads the canonical files
*at the tag* (never the working tree), so a Downloads page built from a later commit still serves
exactly what the tag holds, and writes: the CSV tables, the sub-region GeoJSON, the gazetteer,
CITATION.cff and a short README for the version, SHA256SUMS, and one zip of all of them. The zip is
reproducible (entry timestamps are the tag's commit time; entries sorted), so its checksum is stable.

  python -m pipeline.release assets --out <dir> [--tag vX.Y.Z]   write the files for a tag (default: latest reachable)
  python -m pipeline.release notes [--tag vX.Y.Z]                print the CHANGELOG section for a tag
  python -m pipeline.release latest                              print the latest reachable tag, or nothing

The site build calls the same functions to fill its downloads/ folder and page (web/build.py).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from pipeline import schema

ROOT = Path(__file__).resolve().parent.parent
RELEASE_FILES = ["data/claimants.csv", "data/moves.csv", "data/events.csv", "data/sources.csv", "data/corrections.csv",
                 "data/reference/mavd_subregions.geojson", "data/reference/gazetteer.csv", "data/reference/gazetteer_extra.csv"]
CHANGELOG = ROOT / "CHANGELOG.md"
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")


def _git(root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    except (FileNotFoundError, NotADirectoryError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def latest_tag(root: Path | None = None) -> str | None:
    """The newest release tag reachable from HEAD, or None (no tag, or not a git checkout)."""
    out = _git(root or ROOT, "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*")
    return out if out and TAG_RE.match(out) else None


def tag_date(root: Path, tag: str) -> str:
    """Commit date of the tagged commit (ISO 8601 with offset)."""
    out = _git(root, "log", "-1", "--format=%cI", tag)
    if not out:
        raise RuntimeError(f"tag {tag} not found in {root}")
    return out


def file_at(root: Path, tag: str, path: str) -> bytes:
    r = subprocess.run(["git", "show", f"{tag}:{path}"], cwd=root, capture_output=True)
    if r.returncode:
        raise RuntimeError(f"{path} is not in {tag}: {r.stderr.decode(errors='replace').strip()[:200]}")
    return r.stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def citation_cff(version: str, date: str) -> str:
    """CITATION.cff for a version: the project as the dataset's maintainer, Chubb's work as what it
    continues (references)."""
    return f"""cff-version: 1.2.0
message: "If you use this dataset, cite it together with Andrew Chubb's original work (see references)."
type: dataset
title: "SCS Developments Tracker: assertive moves by claimant states in the South China Sea, 1970 onward"
version: "{version}"
date-released: "{date}"
repository-code: "{schema.REPO_URL}"
url: "https://south-china-sea-developments.github.io/SCS-Developments-Tracker/"
authors:
  - name: "South-China-Sea-Developments project"
  - family-names: "M."
    given-names: "Angelo"
abstract: >-
  A continuation of Andrew Chubb's Maritime Assertiveness Time Series (MATS 1.02, 1970-2015):
  the same coding scheme and unit of analysis (the move), extended forward and to six claimants,
  with a dated, located and sourced event layer under each move. The 1970-2015 moves for China,
  Vietnam and the Philippines are Chubb's, used with permission.
keywords:
  - South China Sea
  - maritime disputes
  - assertiveness
  - event data
references:
  - type: article
    title: "PRC Assertiveness in the South China Sea: Measuring Continuity and Change, 1970-2015"
    authors:
      - family-names: Chubb
        given-names: Andrew
    journal: International Security
    volume: 45
    issue: 3
    start: 79
    end: 121
    year: 2021
    doi: 10.1162/isec_a_00400
  - type: book
    title: "Dynamics of Assertiveness in the South China Sea: China, the Philippines, and Vietnam, 1970-2015"
    authors:
      - family-names: Chubb
        given-names: Andrew
    publisher:
      name: National Bureau of Asian Research
    year: 2022
  - type: data
    title: "Maritime Assertiveness Time Series (MATS 1.0)"
    authors:
      - family-names: Chubb
        given-names: Andrew
    year: 2022
    url: https://mavd.nbr.org
"""


def dataset_readme(version: str, date: str, tag: str) -> str:
    return f"""SCS Developments Tracker, dataset version {version} (tag {tag}, {date[:10]})
{schema.REPO_URL}

Files
  claimants.csv                 claimant codes and names
  moves.csv                     one row per move (the MATS unit of analysis): coding flags, description, provenance
  events.csv                    one row per event: date, place, summary, status, review and harvest provenance
  sources.csv                   one row per source per event
  corrections.csv               documented corrections to MATS-era rows (empty until the author confirms any)
  mavd_subregions.geojson       the ten MAVD sub-region polygons (WGS84)
  gazetteer.csv, gazetteer_extra.csv   named features with coordinates and sub-region (Wikidata, CC0, plus corrections)
  CITATION.cff                  how to cite; SHA256SUMS: checksums of every file here

Column definitions: data/README.md in the repository. Coding rules: Andrew Chubb's methodology appendix (docs/codebook/).

The 1970-2015 moves for China, Vietnam and the Philippines are Andrew Chubb's (MATS 1.02), used with his permission;
any use must cite his work (CITATION.cff, references). Licence for the data: pending agreement with the author;
until a licence file is added, all rights remain with the respective authors.
"""


def assemble(files: dict[str, bytes], tag: str, version: str, date: str, out: Path) -> dict:
    """Write the files plus CITATION.cff, README.txt, SHA256SUMS and the zip into `out`; return the
    manifest {tag, version, date, files: [{name, bytes, sha256}], zip: {name, bytes, sha256}}."""
    out.mkdir(parents=True, exist_ok=True)
    files = dict(files)
    files["CITATION.cff"] = citation_cff(version, date[:10]).encode("utf-8")
    files["README.txt"] = dataset_readme(version, date, tag).encode("utf-8")
    sums = "".join(f"{sha256(b)}  {name}\n" for name, b in sorted(files.items()))
    files["SHA256SUMS"] = sums.encode("utf-8")
    for name, b in files.items():
        (out / name).write_bytes(b)
    stamp = dt.datetime.fromisoformat(date).astimezone(dt.timezone.utc)
    zt = (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)
    zip_name = f"scs-developments-tracker-{tag}.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, b in sorted(files.items()):
            info = zipfile.ZipInfo(f"scs-developments-tracker-{tag}/{name}", date_time=zt)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, b)
    zb = buf.getvalue()
    (out / zip_name).write_bytes(zb)
    manifest = {"tag": tag, "version": version, "date": date,
                "files": [{"name": n, "bytes": len(b), "sha256": sha256(b)} for n, b in files.items()],
                "zip": {"name": zip_name, "bytes": len(zb), "sha256": sha256(zb)}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def build_assets(root: Path, tag: str, out: Path) -> dict:
    """The release files for `tag`, read from git at the tag (never the working tree)."""
    files = {Path(path).name: file_at(root, tag, path) for path in RELEASE_FILES}
    return assemble(files, tag, tag[1:], tag_date(root, tag), out)


def working_assets(data_dir: Path, out: Path, date: str | None = None) -> dict:
    """The same set from the working files, for a site built where no tag is reachable (a pull
    request build, a bundle built from a download). Labelled as unreleased."""
    files = {Path(path).name: (data_dir.parent / path).read_bytes() for path in RELEASE_FILES}
    date = date or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return assemble(files, "unreleased", f"{schema.DATASET_VERSION} (unreleased working copy)", date, out)


def changelog_section(tag: str, changelog: Path = CHANGELOG) -> str:
    """The body of the `## vX.Y.Z` section of CHANGELOG.md, or '' if there is none."""
    if not changelog.exists():
        return ""
    text = changelog.read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(tag)}\b[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("assets"); a_.add_argument("--out", type=Path, required=True); a_.add_argument("--tag", default="")
    n_ = sub.add_parser("notes"); n_.add_argument("--tag", default="")
    sub.add_parser("latest")
    a = p.parse_args(argv)
    if a.cmd == "latest":
        t = latest_tag()
        print(t or "")
        return 0
    tag = a.tag or latest_tag()
    if not tag:
        print("no release tag reachable from HEAD; tag first (docs/releases.md)", file=sys.stderr)
        return 1
    if not TAG_RE.match(tag):
        print(f"{tag!r} is not a release tag (vX.Y.Z or vX.Y.Z-suffix)", file=sys.stderr)
        return 1
    if a.cmd == "assets":
        m = build_assets(ROOT, tag, a.out)
        print(f"{tag}: {len(m['files'])} files and {m['zip']['name']} -> {a.out}")
        return 0
    notes = changelog_section(tag)
    if not notes:
        print(f"CHANGELOG.md has no section '## {tag}'", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
