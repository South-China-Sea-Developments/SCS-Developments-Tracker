# 20: The Airtable workbench

**What to build:** The review base organised the way the maintainer runs his Taiwan Policy Database work ("TPD Updates" sheet): a run log, a source registry, a hand-off view of decided candidates, a place for things seen that are not events, notes across candidates, flags on each candidate and a status that follows it into the dataset.

**Blocked by:** 13

**Status:** built 2026-11-07 (asked for while the ticket 19 backfill was paused for the weekly limit: "start by finishing the architecture"). Live in base `appK9OckCTV15vQwx`; the map of tables and pages, and the push procedure, are in `docs/airtable-workbench.md`.

- [x] Tables `Runs`, `Sources`, `Sidelines`, `Notes` beside `Candidates`; `Candidates` gains `flags`, `dataset_status`, `run` (link), `added_on`, `decided_on`; `Runs` counts `to_decide`, `decided` and a `progress` text from the linked candidates. *Created through the connector; the four existing runs (#17, #24, #31, #33) are rows in `Runs`, the 104 candidates in the base are linked to theirs with flags derived from their machine notes and `dataset_status` = In review; the 93 sources of `pipeline/sources.json` are mirrored.*
- [x] Interface pages: Queue gains *Flagged* and *Added this month* tabs and the new columns; new pages *By claimant*, *Hand-off*, *Run log*, *Sources*, *Sidelines*, *Notes*; Overview gains *Flagged*, *Decided, waiting to be pulled* and a *Runs* section; Candidate Detail shows the new fields. Published.
- [x] The pipeline knows the new fields: `records` emits `flags` (`airtable.flags_for`: excerpt unchecked / not found, source unreachable, possible duplicate, approximate date, low confidence), `dataset_status` In review and, with `--run-record rec…`, the `run` link; a refresh never rewrites `flags` or `run`; `run-record --run harvest/runs/<id> --pr N --notes … --out f.json` emits the `Runs` row (type and date from the run id, counts from `run.json`, excerpt checks and duplicate flags from the candidates, failed sources). Tests in `tests/test_airtable.py`.

**Not done.** `dataset_status` after *In review* is moved by hand (no token for an automated sync); `Sidelines` rows ticked *promote* are not yet read by the import; the `Sources` mirror is refreshed by hand. Runs #24 and #31 have `Runs` rows but their candidates were never pushed to the base (no token at the time); push them with the procedure in `docs/airtable-workbench.md` if the maintainer wants to review them there rather than on their review pages.
