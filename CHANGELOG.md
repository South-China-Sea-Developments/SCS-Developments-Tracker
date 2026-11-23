# Changelog

One section per release tag, newest first. The section's body becomes the GitHub release notes and the "What changed" text on the Downloads page, which renders only paragraphs, flat `- ` bullets and `code` spans; keep to those. Dataset versions follow `MAJOR.MINOR.PATCH`: MAJOR for a change to the coding scheme or the unit of analysis (none planned: ADR 0001, 0002), MINOR for new coverage (years, claimants), PATCH for corrections. The `-dev` suffix marks a dataset still being built.

## Unreleased

- First project-coded moves: `CN201601`–`CN201605` (China, 2016), decided by the maintainer; `CN198201` and `CN200802` extended through 2016 (documented in `data/corrections.csv`).
- Correction: `CN201605` given sub-region 8 (Spratly SW, Fiery Cross Reef), which its decision left blank; the validator now refuses a project move without a sub-region.
- The map counts every event on its sub-region; events with coordinates are drawn at them as well.
- `CN2016xx`–`CN2020xx`: 32 project-coded China moves for 2016–2020 in all, decided by the maintainer; 20 earlier moves extended by continuation notes.
- Retraction: `CN201702` (the 2017 *draft* revision of the Maritime Traffic Safety Law) withdrawn by the maintainer — legislation is coded at enactment (April 2021). The id is retired (`data/reference/retired_moves.csv`) and will not be reused.
- The home page is the assertiveness map (ticket 27): the ten sub-regions shaded by the type-weighted moves of a five-year window (or the build-up since 1970), counts and change arrows, the reefs, shoals and islands the moves name on zoom, a timeline, type / claimant / directed-at filters, decade maps, optional reference lines (Natural Earth), links to a view.
- The other pages in the same style (ticket 28): six menu items (Tracker, Events, Trends, Cases, Methodology, Downloads), a slim banner on inner pages, Issues and domains and Sub-regions merged into Trends (old addresses redirect), short openings, toggle filters.
- Official Asia Society Policy Institute logo on every page; EEZ boundaries from Marine Regions (v12, CC BY 4.0) in place of the indicative zones; 37 more features and more names for 52 others from GeoNames (CC BY 4.0) (ticket 31).
- Every name on the maps in English (ticket 32): 43 features renamed from Chinese, pinyin or Vietnamese, 9 duplicates merged into their English features, event places shown in English (the recorded names are unchanged).
- Candidates without a sub-region come to review with sub-regions suggested from their place (coasts, EEZs, seas, oil blocks) and the reason (ticket 33); new reference files `areas.csv` and `area_points.csv`.
- Moves are also placed by their events' places and coordinates, and by four one-word feature names (ticket 34): 158 of 388 placed (was 144). Thitu Island shown under its English name.
- A page for each reef, shoal or island with moves or a holder, and a By place index (ticket 35); who holds each feature, on the feature pages and as an optional map layer (ticket 36); new reference file `occupation.csv`; Ladd Reef's position corrected.
- A selected sub-region's panel shows its score over every window, with the not-yet-coded years marked (ticket 37).

## v2.0.0-dev — 2026-10-16

First tagged state of the continuation. Not a release for citation in published work: the suffix says the dataset is still being built.

- 357 moves for China, Vietnam and the Philippines, 1970–2015, exactly MATS 1.02 (Andrew Chubb), with the MAVD-only columns and one move (`VN197304`) pending the author's confirmation.
- 125 seed events transcribed from the MAVD `Dates` column (Vietnam), 124 accepted.
- Reference files: the ten MAVD sub-region polygons; a gazetteer of 283 named features from Wikidata with the project's corrections.
- No project-coded moves yet; the harvester, review queue and scheduled run exist and wait for the first live run.
