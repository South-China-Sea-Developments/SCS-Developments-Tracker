# Backfilling 1970–2015 for Malaysia, Indonesia and Taiwan

Decision 03 adds the three claimants with a full 1970–2015 series coded by Chubb's rules. This is the project's own coding (`coded_by = project`), labelled as such on every page and never part of the comparability check, which stays on China, Vietnam and the Philippines. Ticket 12 tracks progress, claimant by claimant and decade by decade.

## What a chunk is

One claimant, one decade (1970s, 1980s, 1990s, 2000s, 2010–2015). A chunk is done when its moves are in `data/moves.csv` with their events and sources, accepted by the coder through the review queue.

## The routine for a chunk

1. **Read the baseline and the previous decade.** `data/baselines/<claimant>.md` gives the pre-1970 level; the previous chunk's accepted moves give the level the new decade is measured against (Chubb's year-on-year rule: a move is an intensification compared with the previous calendar year).
2. **Build the master timeline for the decade** from the archival sources recorded in `pipeline/sources.json` with `kind = archive` (`python -m pipeline.harvest archives` lists them with coverage and access, offline). Every dated, located, sourced incident goes in, confirmed or not, with the source and a verbatim excerpt. Two routes:
   - *Hand-compiled:* write the incidents as a JSON list in the extractor's output shape (see `harvest/manual/README.md`) and run `python -m pipeline.harvest import <file> --run-id <claimant>-<decade> --extractor "<who>"`. The import re-fetches each first source and checks the excerpt, flags duplicates against the dataset, and names the compiler on every candidate.
   - *Extracted:* save each archival document as a capture (one JSON file per document in a folder, with at least `capture_id`, `source_id`, `source_name`, `language`, `url`, `guid`, `title`, `published`, `fetched_at` and the document's `text` — PDFs and scans must be converted to text first; the fetcher does not read archives itself) and run `python -m pipeline.harvest extract --captures <dir> --out harvest/runs/<claimant>-<decade>`; the language model proposes candidates with the usual prompt, and its model and prompt hash are recorded on each.
   - For sources that cannot be fetched from the machine running the import (library databases, paywalled archives), use `--no-fetch`; the candidates then say their excerpt was not checked.
3. **Open the review queue:** `python -m pipeline.queue open --run harvest/runs/<claimant>-<decade>` pushes a branch and opens the pull request with the review page.
4. **The coder decides** every candidate on the review page — reject, merge into an existing move, form a new move with its intensification criterion (novelty, frequency, scope) — exports the decisions and applies them with `python -m pipeline.queue decide`. Suggestions stay on the rows for the agreement report. Nothing is accepted by a machine (ADR 0003). Decision 07 (2026-10-19): No project-coded entry is merged into the dataset until the maintainer has reviewed it himself on its review page; no further candidate sets are compiled or queued until he asks for them. Review PR #17 stays open for his decisions.
5. **Merge the pull request** once the validator is green; the site rebuilds; the chunk's row in the progress table is updated with the number of moves and the date.

## What to watch

- **Year-on-year rule.** A decade's first year is judged against the last year of the previous decade; work chunks in order, or note explicitly when a later decade is coded before an earlier one.
- **State continuity.** Taiwan is the ROC throughout; Malaysia from 1963; Indonesia throughout.
- **Sub-regions.** Malaysian activity falls chiefly in 7 (Spratly SE) and 10 (Far South); Indonesia's in 10, though the Natuna Islands themselves lie outside the ten polygons; Taiwan's in 5 (Taiping) and outside the ten (Pratas). An event outside the ten carries no sub-region and shows on the map only when placed.
- **Comparability.** The validator's comparability rules name `MATS_CLAIMANTS`; nothing here changes the 1970–2015 figures for China, Vietnam or the Philippines, and the tests say so.
- **Diminishment.** Chubb records years in which an aspect of assertiveness fell away; record the same in `diminished_notes` where the sources support it.

## Progress

The table lives in `docs/tickets/12-new-claimants-1970-2015-backfill.md` and is updated with each merged chunk.
