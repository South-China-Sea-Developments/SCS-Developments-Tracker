# SCS Developments Tracker — specification

Confirmed 2026-10-15. Vocabulary: `CONTEXT.md`. Decisions: `docs/adr/`, `docs/decisions/`. Tickets: `docs/tickets/`.

## Problem Statement

Chubb's Maritime Assertiveness Time Series (MATS 1.0) is the only systematic, published measure of claimant assertiveness in the South China Sea, but it stops in 2015, covers three of the six claimants, records time only to the year, has no event locations or structured sources, and lives in a spreadsheet and a 2023 ArcGIS dashboard that nobody updates. A researcher or analyst who wants to know how assertiveness has evolved since 2015, by whom, where and with what evidence, has nothing comparable to turn to.

## Solution

A public, continuously updated database that continues MATS without changing it: the same coding scheme and unit of analysis (the move), extended forward to the present and outward to six claimants, with a new event layer underneath each move carrying dates, locations and sources. Scheduled runs harvest a documented source list and propose candidate events and codings; a human coder decides what enters the dataset. The dataset lives as versioned files in a public repository and is published as a static website with maps, charts, a case browser and downloads, portable to ASPI's host.

## User Stories

1. As a researcher, I want to download the full dataset (moves, events, sources, sub-regions) as CSV/GeoJSON at a tagged version, so that I can cite and reproduce analyses.
2. As a researcher, I want the 1970–2015 moves for China, Vietnam and the Philippines to be exactly MATS 1.02, so that my results are comparable with Chubb's published work.
3. As a researcher, I want each move to show the events inside it, each with a date, a place where known, and linked sources, so that I can verify the coding myself.
4. As a researcher, I want Malaysia, Indonesia and Taiwan coded with the same rules from 1970, so that all six claimants can be compared.
5. As a coder, I want a queue of candidate events harvested from a known source list, each with the source text and link, so that I don't spend my time searching.
6. As a coder, I want a suggested grouping into moves and a suggested MATS coding with reasoning, so that I can accept or correct rather than start from nothing.
7. As a coder, I want to accept, edit or reject each candidate and have only accepted items enter the dataset, with my name and date recorded.
8. As a coder, I want to review in Airtable if I prefer, with my decisions flowing back into the dataset.
9. As a coder, I want the year-on-year rule enforced in the interface: when forming a move, I see the previous year's moves for that claimant and must say which intensification criterion applies (novelty, frequency, scope).
10. As the maintainer, I want a scheduled run that harvests sources, opens a review PR, and opens an issue if it fails, so that the dataset updates without me remembering to run anything.
11. As the maintainer, I want every PR validated (schema, referential integrity, comparability counts) before merge, so that a bad edit can't break the dataset.
12. As the maintainer, I want a report of machine–human coding agreement over time, so that I can judge the suggestions and defend the method.
13. As a public visitor, I want to see assertive moves by claimant and year, by type, by issue and domain, and by sub-region, so that I can grasp trends at a glance.
14. As a public visitor, I want a map of event locations with a time slider and filters, so that I can see where things happen.
15. As a public visitor, I want to open a move and read its description, coding, events and sources, so that the numbers are backed by evidence.
16. As the original author, I want to be credited on every page and able to check that the 1970–2015 figures match his, so that the continuation is trustworthy.
17. As ASPI's web team, I want a self-contained static bundle with relative paths, so that it can be hosted on our site without a server.

## Implementation Decisions

**Repository layout.** One repository holds canonical data, the pipeline, the site, tests and documentation (ADR 0004). Project memory lives in committed docs: glossary, ADRs, decision map, spec and tickets.

**Canonical tables** (CSV, UTF-8, header row, one record per row; all identifiers stable once published):

- `claimants` — `code` (CN, VN, PH, MY, ID, TW), `name`.
- `moves` — one row per move. `move_id` (MATS form: claimant code + year + two-digit instance, e.g. `CN201105`), `claimant`, `year`, `instance_no`; Type flags `declarative`, `demonstrative`, `coercive`, `force` (0/1); Domain flags `domestic`, `diplomatic`, `physical`; Issue flags `military`, `administrative`, `energy`, `fisheries`, `politics`; Sub-region flags `loc01_tonkin` … `loc10_far_south`; `dyads` (space-separated MATS codes, actor first); `description` (narrative with inline citations, as MATS); `ongoing_through`, `ongoing_through_notes`; `diminished_notes`, `other_possible_cases` (from the MAVD table where present); `intensification_criterion` (novelty | frequency | scope; empty for MATS-era moves unless stated); `org_case_no`; provenance: `coded_by` (`chubb` | `project`), `coder`, `coding_date`, `data_version`, `status` (`accepted` | `pending`). The MATS packed codes (`Domains`, `Issues`, `Locations`) are not stored; they are derived from the flags on export and checked by the validator.
- `events` — one row per event. `event_id`; `move_id` (empty while a candidate); `claimant`; `date_start`, `date_end`, `date_precision` (day | month | year); `lat`, `lon`, `location_name`, `location_precision` (point | feature | subregion | unknown); `subregion` (1–10 or empty); `summary`; `actors` (free text, e.g. "CCG 5901; PCG BRP Teresa Magbanua"); `status` (candidate | accepted | rejected | merged); harvest provenance: `harvest_run_id`, `extractor` (model identifier and prompt hash, or `manual:<compiler>` for hand-compiled candidates); suggestions: `suggested_move_id`, `suggested_type`, `suggested_domains`, `suggested_issues`, `suggested_dyads`, `suggestion_reasoning`; review: `reviewer`, `review_date`, `review_note`.
- `sources` — one row per source per event. `source_id`, `event_id`, `url`, `title`, `publisher`, `pub_date`, `language`, `accessed_date`, `archive_url` (Wayback or equivalent), `excerpt` (the passage that supports the event).
- `subregions` (GeoJSON) — the ten MAVD polygons, `LocationNo` 1–10, unchanged.
- `baselines` — per claimant, the pre-1970 actions that form the zero-baseline (Chubb's PRC list; new lists for the other five), as a markdown document per claimant rather than a table.

**Loading MATS 1.02.** The author-supplied xlsx is authoritative for the 357 CN/VN/PH moves 1970–2015 (`coded_by = chubb`, `data_version = 1.02`). From the MAVD online table, the columns the xlsx lacks (`Dates`, `Other_Possible_Cases`, diminished cases) are imported; `Dates` becomes a seed event with `date_precision` as given. Where the online description differs from the xlsx (75 moves), the xlsx text is used and the difference logged for the author. `VN197304`, present online but not in the xlsx, is loaded with `status = pending` until the author confirms. These are the only edits ever applied to MATS-era rows without a documented correction.

**Harvester.** A registry of sources (name, URL or feed, type, language, claimant coverage, cadence) is a committed, documented file. Each run fetches new items since the last run, saves raw captures, and passes them to an extractor that returns zero or more candidate events in the schema above, each with at least one source and an excerpt. The extractor is a language model with a fixed prompt built from the codebook; prompt and model identifier are recorded on every candidate. Deduplication against existing events is by claimant, date window and location/summary similarity, with duplicates surfaced to the reviewer rather than silently dropped. Each run opens one pull request containing its candidates.

**Review queue.** The PR is the queue. A review page (static, generated from the PR's candidates) presents each candidate with its source excerpt and link, the suggestions, and the claimant's previous-year moves; the coder's decisions (accept with edits / reject / merge into existing move / form new move with criterion) are written back as commits to the PR. The optional Airtable front end mirrors the same candidates and writes the same decisions back; it is never read when building the dataset or the site.

**Validator.** A command that reads the canonical files and fails on: schema violations; unknown codes; a move with no Type flag set; an event whose `move_id` does not exist (unless candidate); a source whose `event_id` does not exist; an accepted event without a source; duplicate identifiers; and comparability failures — per-claimant-year move counts and per-Type totals for CN/VN/PH 1970–2015 must equal the MATS 1.02 totals (and `coded_by = chubb` rows must be byte-identical to the loaded original apart from documented corrections). Runs on every PR and blocks merge.

**Site.** A static bundle built from the canonical files. Pages: overview (moves by claimant and year, by Type); issues and domains; sub-regions (choropleth over the ten polygons, five-year bins as MAVD); event map (points with time slider and Type/Domain/Issue/Dyad/claimant filters); case browser (searchable list → move detail with description, coding, events, sources); downloads and citation; methodology (codebook summary, provenance, agreement report). The build emits the aggregated JSON the charts use; the validator recomputes the same aggregates independently. Relative paths only; no runtime dependency on the host. Visual style new and ASPI-compatible; MAVD's chart types retained where they aid comparison.

**Scheduling and operations.** The harvester runs weekly on the repository's CI; the site rebuilds on every merge to `main`; a failed run opens an issue. The extractor's API key is a repository secret and the only running cost; the first harvest ticket measures it. Releases are tags; the Downloads page links the latest tag.

**Agreement log.** Because suggestions stay on the event/move rows, the agreement report is a derived file: for each accepted move, suggested versus final Type/Domain/Issue, summarised by period and by extractor version.

## Testing Decisions

Three seams, agreed: (1) the canonical files, via the validator — schema, integrity, and comparability against MATS 1.02 totals; this is the merge gate; (2) the harvester, on fixtures — a frozen folder of saved source pages must yield an expected candidate set, with no network in tests; the extractor is tested through a recorded-response layer so tests are deterministic; (3) the site build — aggregates emitted for the charts must equal the validator's, and every page renders without console errors in a headless browser. The review page, Airtable sync and CI wiring are verified only through seam 1 (what lands in the files). Tests are the project's first code: each ticket starts with its failing check. Python with pytest for the pipeline and validator; the site's checks run in the same suite via a headless browser.

## Out of Scope

- Changing any MATS variable's definition or the year-on-year unit (ADR 0001, 0002).
- Cooperative or conciliatory actions (excluded by Chubb's framework).
- Non-claimant actors (United States, Japan, Australia, India) as coded actors; they remain context in descriptions.
- Brunei as a coded claimant; other maritime theatres (East China Sea).
- Automatic acceptance of any event or move (ADR 0003).
- Republishing to ArcGIS Online; a server-side database; user accounts on the site.
- Weighting moves by significance (explicitly not done in MATS).

## Amendments

- 2026-10-15 (ticket 06): the validator's move rule reads "an event with a `move_id` must point at an existing move of the same claimant and year; an accepted or merged event must have one; a candidate or rejected event may have none". Rejected events keep no move, so the original wording (any non-candidate needs a move) is relaxed for them. Event status `merged` means "judged a duplicate report of an accepted event; attached to that event's move". A rejected event needs a review note; a project-coded move needs its intensification criterion.

- 2026-10-15 (ticket 07): the scheduled run's operations (`pipeline/ops.py`: harvest state branch, failure issue, reminders) are tested against a fake GitHub API and a local bare remote, outside the three seams; the workflow file itself is verified only by a dispatched dry run. Harvest state lives on a `harvest-state` branch that is never merged (decision 08).
- 2026-10-15 (ticket 08): `location_precision = feature` means the sources name a feature; the event has coordinates when the gazetteer (`data/reference/gazetteer.csv` + `gazetteer_extra.csv`, a reference file like the polygons) knows the name, and `point` means the coordinates are the event's own. The validator gains a LOCATION rule: a `point` has coordinates; one coordinate never comes without the other; a stated sub-region is the one the coordinates fall in. Placement is a lookup, not a coding judgment: coordinates are trusted over a name and a name over an extractor-stated sub-region, so `queue open` may replace the extractor's sub-region on a candidate; a reviewer's typed sub-region is kept for the validator to judge. On the event map an event without coordinates counts once on its own sub-region or, having none, once on each sub-region of its move (MATS-era seed events carry no location of their own), so the polygon numbers can sum to more than the events. The map shows accepted events of accepted moves only. Tests: `pipeline.gazetteer` (resolution, placement) and `queue._check_edits` are unit-tested outside the three seams; `queue open` and the LOCATION rule at seam 1; the map's data, markers and controls at seam 3.

- 2026-10-16 (ticket 09): a release is a tag `vX.Y.Z[-suffix]` on `main`; the Downloads page and the GitHub Release serve the dataset files as they are at the tag (read from git, never the working tree) with checksums, a reproducible zip, `CITATION.cff` and the changelog section, from inside the site bundle; a build with no reachable tag serves the working files labelled unreleased and offers no citation. `pipeline.release` is tested against a temporary tagged repository, outside the three seams; the release workflow is verified by the first real tag.

- 2026-10-18 (ticket 10): the agreement report's unit is the accepted event carrying a suggestion, compared with its move's final coding (one row per event, so a move formed from several candidates counts once per candidate); "period" is the event's calendar year, not the five-year MAVD bin. It also reports dyads, grouping where an extractor proposed a move, the outcome of every decided suggestion, and a Type confusion matrix. `pipeline.agreement` is unit-tested against a hand-counted fixture outside the three seams; at seam 3 the build emits `data/agreement.json` and the methodology page renders the tables without console errors.

- 2026-10-18 (ticket 11): baselines live in `data/baselines/<claimant>.md` and ship with every release. Candidates may also be compiled by hand (a researcher's or an assistant's reading of sources, in the extractor's output shape with a `sources` list per event) and imported with `pipeline.harvest import`, which runs them through the extractor's normalisation, fetches each first source to check the excerpt (or says why it could not), flags duplicates, and records `manual:<compiler>` as the `extractor` (no prompt was used, so no prompt hash; the compiler may be a person or an assistant model, named as given); such rows appear as their own extractor version in the agreement report. They then enter the review queue like any harvested candidate (ADR 0003 unchanged: nothing is accepted by a machine). The compiled sets are kept under `harvest/manual/`; the first is the 2016+ candidate set for MY, ID and TW.

- 2026-10-19 (ticket 12): the source registry also records archives (`kind: archive`: chronologies, yearbooks, government and legal deposits, press archives, scholarly works) with coverage years, access and how to use them; the harvester lists them and never fetches them. The backfill routine is `docs/backfill.md`. On the maintainer's instruction of 2026-10-19, no project-coded entry (any claimant) enters the dataset or the review queue until he has reviewed it himself; review PR #17 stays open for his decisions.

## Further Notes

- Build order: tracer bullet first (load MATS 1.02 → validator → first site pages reproducing MAVD's counts), then the harvester and review queue on CN/VN/PH 2016+, then the event map, then the three new claimants' 1970–2015 backfill, then Airtable.
- The author should be asked early about: the xlsx/online discrepancies, `VN197304`, the data licence, his preferred credit line, and whether his suggested dataset citation (version 1.01, May 18) should read 1.02 for the file he supplied. These do not block the tracer bullet.
- The project's memory files (spec, tickets, decisions) are committed under `docs/` rather than an ignored scratch folder, so that fresh sessions and collaborators find them.
