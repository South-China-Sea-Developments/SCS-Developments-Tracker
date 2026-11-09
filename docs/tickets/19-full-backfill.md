# 19: The full backfill — three new claimants 1970–2015, all six claimants 2016–October 2026

**What to build:** Candidate-event sets for every claimant and period not yet covered, compiled from opened sources with verbatim excerpts and queued as review pull requests for the maintainer's decisions: Malaysia, Indonesia and Taiwan for 1970–2015 (fifteen claimant-decade chunks, the routine of `docs/backfill.md`), and all six claimants from 2016 to the end of October 2026 (twelve claimant-period chunks, 2016–2020 and 2021–Oct 2026). The maintainer asked for the whole run on 2026-11-07 ("run the entire search for all episodes for each of the not-yet-included claimants and then backlog from 2015 to the end of October 2026"), which lifts decision 07's "no further candidate sets until he asks". Decision 03's sequencing gate (the first CN/VN/PH 2016+ review proves the routine) is met in spirit by running one chunk first as a pilot and fixing the routine before the rest.

**Blocked by:** 11, 12, 13

**Status:** in progress (2026-11-07).

**Method:** one research agent per chunk, briefed by `harvest/manual/BRIEF.md`, writes `harvest/manual/<date>-<claimant>-<period>.json`; `python -m pipeline.harvest import <file> --run-id <claimant>-<period> --extractor "research agent (claude-fable-5-1) for ticket 19"` re-fetches each first source and checks the excerpt, flags duplicates against the dataset and the earlier candidates of the set; `python -m pipeline.queue open --run harvest/runs/<run-id>` opens the review pull request; `python -m pipeline.airtable push` mirrors it to the review board. The maintainer decides on the board or the review page; nothing is merged by the machine. Review PR #17 (24 candidates for MY/ID/TW 2016+) is superseded by the fuller MY/ID/TW 2016–2020 and 2021–2026 sets, which fold its 24 in; it is closed with a comment when those open.

- [x] Pilot: PH 2016–2020 compiled, imported, queued; the routine's problems (excerpt checks, fetch failures, duplicate flags, volume) fixed before the rest. *80 candidates (47 declarative, 26 demonstrative, 6 coercive, 1 force), 74 excerpts verified against the re-fetched first source, 5 unchecked (PDF or unfetchable), 1 not found, 6 possible-duplicate flags; review PR #33. Cost of the compile: about 410k tokens and 48 minutes for one claimant-period — the whole run is of the order of 11 million tokens.*
- [ ] 2016–2020 and 2021–Oct 2026 for CN, VN, PH, MY, ID, TW: twelve chunks queued.
- [ ] 1970s, 1980s, 1990s, 2000s, 2010–2015 for MY, ID, TW: fifteen chunks queued, in decade order per claimant.
- [ ] Ticket 12's progress table and this one's record each chunk's PR number and candidate count; `docs/sources/baselines-and-manual-candidates.md` and `harvest/manual/README.md` list every file.

| Chunk | Candidates | Review PR | Notes |
|---|---|---|---|
| VN 2016–2020 | 107 | #43 | 52/107 excerpts verified, 50 unchecked (Vietnamese sites block the importer's fetcher; the agent verified 62 itself); 4 possible duplicates; yearly moratorium rejections one event a year |
| PH 2016–2020 | 80 | #33 | pilot; 74/80 excerpts verified |
| CN 2016–2020 | 93 | #41 | 88/93 excerpts verified; 3 possible duplicates; US-directed acts kept as one event a year (dyad CU) for the coder to keep or drop |
| MY 2016–2020 | 40 | #38 | 27/40 excerpts verified, 12 unchecked (scans, PDFs); overlaps #17 (West Capella, CLCS submission, Jul 2020 note) |
