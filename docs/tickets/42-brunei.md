# 42 — Brunei, the seventh claimant

Asked by the maintainer on 2026-11-22 ("add Brunei everywhere") and started on 2026-11-23. Decision
(2026-11-23): Brunei's series starts in 1970 like the others; the Sultanate's own acts count from 1970,
and British acts for Brunei are baseline context (decision 03, amendment of 2026-11-23).

- Code: `BN` in `pipeline/schema.py` and `data/claimants.csv`, so the validator, extractor, review page,
  Airtable push and every site page (selectors on the map, cases, trends and home pages; claimant maps)
  carry it. Colour: categorical slot 7, violet `#6250d6` (validated with the dataviz palette checker,
  light surface: CVD worst adjacent ΔE 9.1, normal-vision 19.6; the contrast warning is the existing one
  for aqua, yellow and magenta). Airtable choice colour `cyanLight2`.
- The extraction prompt names seven claimants; the harvest fixture's recordings are re-keyed to the new
  prompt hash (`16894699d5d2`).
- `data/baselines/BN.md`: pre-1970 actions (the Sultan's 1954 continental-shelf proclamation, the 1958
  Orders in Council, the first offshore licensing), with sources; released as `BASELINE-BN.md`.
- Candidates: `harvest/manual/20261123-BN-1970-2026.json`, 13 sourced events 1980–2023 (two British
  protests on Brunei's behalf, the 1983 fishery-limits and territorial-waters acts, the 1984 definition of
  the territory, the 1987 and 1988 maps, the 1993 EEZ, Blocks J and K in 2003, the 2009 Exchange of
  Letters and outer-shelf filing, the 2020 and 2023 statements), opened as run `BN-1970-2026` for review
  in Airtable.

Status: built; candidates await the maintainer's review.
