# 06: Review queue as pull request, with review page

**What to build:** A harvest run opens a pull request of candidates; the coder reviews them on a generated page and their decisions become commits; only accepted events reach the files, with reviewer and date, and the validator gates the merge.

**Blocked by:** 05

**Status:** ready

- [ ] A run opens one PR adding its candidates to `events` and `sources`.
- [ ] A review page is generated for the PR showing, per candidate: summary, source excerpt and link, suggested move/coding with reasoning, duplicates flagged, and the claimant's moves from the previous year.
- [ ] Decisions supported: accept (with edits), reject (with note), merge into an existing move, form a new move (requires `intensification_criterion`); each decision is written back as a commit to the PR.
- [ ] On merge, accepted events carry `reviewer`, `review_date`, `status = accepted`; rejected ones carry `status = rejected` and stay in the files for the agreement log.
- [ ] The validator blocks merge when any accepted event lacks a source or a move.
- [ ] Seam-1 test: a fixture PR reviewed with each decision type yields the expected file state.
