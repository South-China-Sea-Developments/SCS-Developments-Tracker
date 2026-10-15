# 06: Review queue as pull request, with review page

**What to build:** A harvest run opens a pull request of candidates; the coder reviews them on a generated page and their decisions become commits; only accepted events reach the files, with reviewer and date, and the validator gates the merge.

**Blocked by:** 05

**Status:** done (2026-10-15, PR #6)

- [x] A run opens one PR adding its candidates to `events` and `sources`.
- [x] A review page is generated for the PR showing, per candidate: summary, source excerpt and link, suggested move/coding with reasoning, duplicates flagged, and the claimant's moves from the previous year.
- [x] Decisions supported: accept (with edits), reject (with note), merge into an existing move, form a new move (requires `intensification_criterion`); each decision is written back as a commit to the PR. *Accepting is always into a move: "merge" (existing) or "new move"; edits ride on either. Decisions are made on the static review page, exported as JSON, applied and committed with `pipeline.queue decide`.*
- [x] On merge, accepted events carry `reviewer`, `review_date`, `status = accepted`; rejected ones carry `status = rejected` and stay in the files for the agreement log.
- [x] The validator blocks merge when any accepted event lacks a source or a move. *Also: a rejected event needs a note; a project-coded move needs its intensification criterion.*
- [x] Seam-1 test: a fixture PR reviewed with each decision type yields the expected file state.
