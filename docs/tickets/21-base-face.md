# 21: The face of the base

**What to build:** The review base's tables look like the maintainer's other Airtable bases (his PLA Daily base, grid view "group by service", was the reference): readable column names, coloured select chips, a rating and a tick for his own triage, grid views sorted by date.

**Blocked by:** 20

**Status:** built 2026-11-07. Map in `docs/airtable-workbench.md` ("The face of the table").

- [x] Coloured selects replace text and grey selects on `Candidates`: `Claimant`, `Suggested type`, `New move: type`, `Date precision`, `Sub-region`, `Suggested domains`, `Suggested issues`, `Suggested dyads` (the last three multi-selects); the 104 records migrated; the old columns renamed `zz old …` for the maintainer to delete (the connector cannot delete fields). `Priority` (rating, 3 stars) and `Selected` (checkbox) added for the reviewer's own triage; the sync never writes them.
- [x] Readable names on every field of `Candidates`, `Runs`, `Sources`, `Sidelines`, `Notes`; the grid view of each table configured (Candidates "Time-sorted": Selected, Priority, Claimant, Start date, precision, type, location, sub-region, summary, flags, decision…, newest first).
- [x] Interface pages repointed to the new fields (Queue, By claimant, Board, Overview charts and dropdowns, Hand-off, Candidate Detail; Review one by one recreated as `pagMBrGwofJENJ3o6`).
- [x] The pipeline speaks the base's new shape: `FIELDS` carries the select types and colours (`table_schema` prints them, with each field's `label`); `LABELS` maps internal names to the base's column names; the REST client translates at the wire by field id when the configuration has them (`returnFieldsByFieldId` on reads), so renames in the base change nothing; `records` sends lists for the three multi-selects; `run_filter` names the run column by its label. Tests in `tests/test_airtable.py`.

**Not done.** Only one grid view per table can be configured through the connector; the maintainer duplicates "Time-sorted" for other slices. Colours of the older coder selects (`New move: criterion`, `Edit: …`) are unchanged (rarely shown).
