# Releases

A release is a git tag on `main`. Tagging is the only manual step; everything a researcher downloads or cites is derived from the tag.

## What a release is

- The tag `vX.Y.Z` (or `vX.Y.Z-dev` while the dataset is being built) on a commit of `main` that passes the validator.
- `CHANGELOG.md` has a `## vX.Y.Z — YYYY-MM-DD` section describing what changed; it becomes the release notes.
- `pipeline/schema.py` `DATASET_VERSION` equals `X.Y.Z` (it is written onto every project-coded move as `data_version`), and `CITATION.cff` at the repository root carries the same version and date.
- The GitHub Release (created by the `release` workflow from the tag) holds the dataset files *as they are at the tag*, CITATION.cff, a README, `SHA256SUMS` and one zip of all of them, reproducibly built so the checksums are stable.
- The site's Downloads page serves the same files from inside the bundle (`downloads/` in the build), so a copy of the site on another host needs nothing from GitHub.

Version numbers: MAJOR for a change to the coding scheme or the unit of analysis (ADR 0001 and 0002 say there will be none), MINOR for new coverage (a year, a claimant), PATCH for corrections to existing rows.

## Procedure

1. On `main`, with the validator green (`python -m pipeline.validate`), set `DATASET_VERSION` in `pipeline/schema.py`, update `version` and `date-released` in `CITATION.cff`, and add the `## vX.Y.Z — date` section to `CHANGELOG.md`. Open and merge that as a pull request like any other change.
2. Tag the merge commit and push the tag:
   ```
   git checkout main && git pull
   git tag -a vX.Y.Z -m "Dataset vX.Y.Z"
   git push origin vX.Y.Z
   ```
3. The `release` workflow runs the validator at the tag, builds the assets with `python -m pipeline.release assets`, and creates the GitHub Release with the CHANGELOG section as notes. The `publish site` workflow also runs on the tag push, so the Downloads page shows the new version within minutes.
4. Check the release page and the Downloads page. If something is wrong, fix it on `main`, delete the tag and the release, and tag again; never move a tag that anyone may have cited.

`python -m pipeline.release latest` prints the newest tag reachable from the current commit; `python -m pipeline.release notes` prints its CHANGELOG section.
