# 09: Downloads, citation and tagged releases

**What to build:** A researcher downloads the dataset at a tagged version and copies a citation that credits both the project and Chubb.

**Blocked by:** 02

**Status:** done (2026-10-15, PR #11)

- [x] Downloads page lists CSV files, the sub-region GeoJSON and a combined zip for the latest tag, with checksums. *`pipeline/release.py` reads the files at the newest reachable tag with `git show` (never the working tree), adds CITATION.cff, a README and SHA256SUMS, and writes a reproducible zip (entry times = the tag's commit time); the site build puts all of it in `downloads/` inside the bundle, so the page works on any host without GitHub, and links the GitHub release as the mirror. Also the gazetteer files. A build with no reachable tag (a pull-request build, a downloaded bundle) serves the working files labelled "unreleased working copy".*
- [x] Citation block for the project (with version and date) and Chubb's required citations. *Plain text and BibTeX, generated from the tag; `CITATION.cff` at the repository root (GitHub's "Cite this repository") and in every download; Chubb's three citations and the Dataverse appendix listed alongside; the methodology page points here.*
- [x] A documented release procedure: tag, changelog entry, Downloads page updated automatically. *`docs/releases.md`; `CHANGELOG.md` with one section per tag (its body is the release notes and the page's "What changed"); `.github/workflows/release.yml` validates at the tag and creates the GitHub Release with the assets; `pages.yml` also runs on tag pushes. A test holds `CITATION.cff`, `CHANGELOG.md` and `pyproject.toml` to `DATASET_VERSION`.*
- [x] First tag `v2.0.0-dev` created. *Tagged on the merge commit of this ticket; the `-dev` suffix is explained on the page and marks the release as a pre-release on GitHub.*

Tests: `tests/test_release.py` (assets come from the tag not the working tree, checksums verify, the zip is reproducible, the page says which version it serves, the no-tag fallback) against a temporary tagged repository; site renders in `tests/test_site.py`.
