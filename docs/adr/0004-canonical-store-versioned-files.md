# 0004. Canonical store: versioned files in the repository; Airtable only as a review front end

Date: 2026-10-15. Status: accepted.

## Context

The dataset needs a canonical home that supports a review queue (ADR 0003), a public site, scheduled runs, citation, and forking by other researchers, at no cost while the project is exploratory and unfunded.

## Decision

The canonical data are **plain files in this repository** under `data/`: moves, events and sources as CSV (UTF-8, one row per record) and reference geometry as GeoJSON. A record exists only if it is in the files on the main branch.

The **review queue is a pull request**: a scheduled run opens one PR per harvest containing candidate events (and suggested moves/coding) as additions to the files; the coder edits and merges; merging is acceptance. The public site is rebuilt from the files on every merge.

**Airtable may be used as a front end for the review queue only**: candidates are pushed into an Airtable base for a friendlier reviewing experience, and the reviewer's decisions are written back into the PR. Airtable never holds data that is not also in the repository, and nothing reads Airtable to build the dataset or the site.

## Alternatives considered

- **Hosted database (Postgres) as canonical.** Rejected for now: a service to run, credentials to protect, and a bill once past the free tier, for a benefit (multi-user web editing) the project does not yet need. The files remain the interchange format, so moving later is an export, not a migration.
- **Airtable or Google Sheets as canonical.** Rejected: schema outside version control, weak history, row caps on the free tier, and the dataset could not be cited at a fixed version.

## Consequences

- Every change to the dataset is a diff with an author and a date; a release is a tag; a citation can name a commit.
- Schema changes are migrations of CSV files, reviewed like any other change.
- The Airtable sync is optional tooling and must be safe to switch off at any time.
- Large binary sources (PDF captures of cited pages) are stored outside git or via Git LFS if they are kept at all; the repository holds references.
