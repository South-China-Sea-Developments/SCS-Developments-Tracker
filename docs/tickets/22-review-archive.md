# 22: The review archive

**What to build:** Reviewed candidates leave the Airtable base (which hit the free plan's 1,000-record
cap on 17 Nov 2026) without losing anything the coder typed: the rows are filed in the repository first,
the decisions applied from that file, the rows deleted, and the run's row in the run log says where the
archive is. ADR 0005.

**Blocked by:** 20, 21

**Status:** built 2026-11-17.

- [x] `pipeline.airtable archive --run <run_id> --from export.json [--out-dir …] [--reviewer] [--date]` writes
  `harvest/airtable/<run_id>/records.json` (every exported row of the run, code's field names, Airtable id,
  coder's columns; merged by event id with an earlier file so partial reviews accumulate), `decisions.json`
  (the decided rows, for `queue decide`) and `clear.json` (the decided rows' Airtable ids to delete).
  Offline; never calls Airtable. A decision archived in an earlier sitting is not re-emitted; two rows for one event
  refuse; an export with no row of the run exits 1; the triage columns `Priority`/`Selected` are read by label or by
  `triage_field_ids`. Tests in `tests/test_airtable.py` (six `test_archive_*`).
- [x] `Runs` table: `archived_on` (date) and `archive` (URL of the folder on GitHub), filled by hand through
  the connector at archive time.
- [x] Procedure "After review: archive and clear" in `docs/airtable-workbench.md`; step 4a in `docs/backfill.md`;
  glossary entry in `CONTEXT.md`.

**Not done.** The deletion and the Runs update go through the maintainer's connector in a Claude session
(no token, by decision); `clear` with a token does the same deletion for a whole run but does not archive —
use `archive` first.
