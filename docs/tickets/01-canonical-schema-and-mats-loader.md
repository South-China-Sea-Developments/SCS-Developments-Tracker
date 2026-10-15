# 01: Canonical schema and MATS 1.02 loader

**What to build:** The canonical files exist with the agreed columns (`claimants`, `moves`, `events`, `sources`, plus the sub-region GeoJSON already in `data/reference/`), filled from MATS 1.02 and the MAVD online table. A validator command passes on them and fails on a deliberately broken copy, and runs on every pull request so nothing invalid can merge.

**Blocked by:** None, can start immediately

**Status:** done (2026-10-15, PR #1)

- [x] `claimants` lists CN, VN, PH, MY, ID, TW.
- [x] `moves` holds exactly 357 rows with `coded_by = chubb`, `data_version = 1.02`, `status = accepted`: CN 144, VN 111, PH 102; per-Type totals equal those computed from the xlsx (Declarative 90, Demonstrative 175, Coercive 75, Force 17); all flag columns reproduce the xlsx packed codes `Domains`, `Issues`, `Locations` exactly. *Exception recorded:* `PH197701` has `Domains = 3` in the xlsx but all three Domain flags 0; the flags are loaded as given and the inconsistency is logged for the author. Text cells are whitespace-stripped (57 cells), otherwise byte-identical.
- [x] `VN197304` is loaded from the MAVD table with `status = pending`; it is excluded from the comparability counts.
- [x] `diminished_notes` and `other_possible_cases` are filled from the MAVD table where present (57 and 77 moves).
- [x] Each MAVD `Dates` value (103 moves) becomes seed events — **one per `;`-separated date token, 125 in all** (a value such as `1973/01/29; 1973/05/07; …` lists separate incidents) — with `date_precision` reflecting what the text gives, `status = accepted` (`candidate` for the pending move), and a source row pointing at the MATS description. Three seed dates fall outside their move's year (likely MAVD typos); they are loaded as given, noted on the event and listed in the report.
- [x] The 75 description differences between xlsx and MAVD are written to a log file for the author; the xlsx text is what `moves.description` holds.
- [x] The validator fails on each of: schema violation, unknown code, move with no Type flag, event with a non-existent `move_id` (non-candidate), source with a non-existent `event_id`, accepted event without a source, duplicate id, and any departure of the CN/VN/PH 1970–2015 counts from the figures above (counted over all accepted moves in that scope, whoever coded them; plus field-level identity of every MATS-era row bar documented corrections in `corrections.csv`).
- [x] The validator runs in CI on every pull request and on `main`.
- [x] Tests are written first; the full suite passes; the loader is re-runnable and idempotent.
