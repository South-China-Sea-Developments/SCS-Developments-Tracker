# 01: Canonical schema and MATS 1.02 loader

**What to build:** The canonical files exist with the agreed columns (`claimants`, `moves`, `events`, `sources`, plus the sub-region GeoJSON already in `data/reference/`), filled from MATS 1.02 and the MAVD online table. A validator command passes on them and fails on a deliberately broken copy, and runs on every pull request so nothing invalid can merge.

**Blocked by:** None, can start immediately

**Status:** ready

- [ ] `claimants` lists CN, VN, PH, MY, ID, TW.
- [ ] `moves` holds exactly 357 rows with `coded_by = chubb`, `data_version = 1.02`, `status = accepted`: CN 144, VN 111, PH 102; per-Type totals equal those computed from the xlsx (Declarative 90, Demonstrative 175, Coercive 75, Force 17); all flag columns reproduce the xlsx packed codes `Domains`, `Issues`, `Locations` exactly.
- [ ] `VN197304` is loaded from the MAVD table with `status = pending`; it is excluded from the comparability counts.
- [ ] `diminished_notes` and `other_possible_cases` are filled from the MAVD table where present (57 and 77 moves).
- [ ] Each MAVD `Dates` value (103 moves) becomes one seed event with `date_precision` reflecting what the text gives, `status = accepted`, and a source row pointing at the MATS description.
- [ ] The 75 description differences between xlsx and MAVD are written to a log file for the author; the xlsx text is what `moves.description` holds.
- [ ] The validator fails on each of: schema violation, unknown code, move with no Type flag, event with a non-existent `move_id` (non-candidate), source with a non-existent `event_id`, accepted event without a source, duplicate id, and any departure of the CN/VN/PH 1970–2015 counts from the figures above.
- [ ] The validator runs in CI on every pull request and on `main`.
- [ ] Tests are written first; the full suite passes; the loader is re-runnable and idempotent.
