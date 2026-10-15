# Canonical data

These files are the dataset. A record exists only if it is here, on `main` (ADR 0004). Column definitions: `docs/spec.md` ("Canonical tables"); vocabulary: `CONTEXT.md`; coding rules: `docs/codebook/`.

| File | One row per | Notes |
|---|---|---|
| `claimants.csv` | claimant state | CN, VN, PH, MY, ID, TW |
| `moves.csv` | move (MATS unit) | 357 accepted moves from MATS 1.02 (`coded_by = chubb`, `data_version = 1.02`) plus `VN197304` (`status = pending`, from the MAVD table, awaiting the author's confirmation). Flags are 0/1; MATS packed codes are derived, not stored. |
| `events.csv` | event | Currently 125 seed events for Vietnamese moves, one per date token in the MAVD `Dates` column. |
| `sources.csv` | source per event | Seed events cite the MATS case description. |
| `corrections.csv` | documented correction to a MATS-era row | Empty. Any change to a `coded_by = chubb` field must be listed here (move, field, new value, date, by, reason) or the validator rejects it. |
| `reference/mavd_subregions.geojson` | sub-region polygon | Ten MAVD polygons, `LocationNo` 1–10. |
| `raw/` | — | Inputs as received. Never edited. |

Regenerate from raw inputs: `python -m pipeline.load_mats`. Check: `python -m pipeline.validate`. CI runs both on every pull request and refuses a merge that fails either, or whose files differ from a fresh regeneration.

Differences between the author's xlsx and the MAVD online table (75 descriptions, 19 flags, 1 internal inconsistency) are listed in `docs/reports/mats-1.02-vs-mavd-differences.md` for the author's review; the xlsx value is used throughout.
