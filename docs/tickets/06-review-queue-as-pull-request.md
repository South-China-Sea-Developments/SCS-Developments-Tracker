# 06: Review queue as pull request, with review page

**What to build:** A harvest run opens a pull request of candidates; the coder reviews them on a generated page and their decisions become commits; only accepted events reach the files, with reviewer and date, and the validator gates the merge.

**Blocked by:** 05

**Status:** done (2026-10-15, PR #6)

- [x] A run opens one PR adding its candidates to `events` and `sources`.
- [x] A review page is generated for the PR showing, per candidate: summary, source excerpt and link, suggested move/coding with reasoning, duplicates flagged, and the claimant's moves from the previous year.
- [x] Decisions supported: accept (with edits), reject (with note), merge into an existing move, form a new move (requires `intensification_criterion`); each decision is written back as a commit to the PR. *Accepting is always into a move: "merge" (an existing move, or one formed from another candidate in the same batch) or "new move"; a report of the same incident is a "duplicate" (status merged); edits ride on any of them and are validated. Decisions are made on the static review page, exported as JSON, and applied all-or-nothing by `pipeline.queue decide`, which runs the validator before writing and makes one commit per batch (listing the events). A terminal is still needed for that step, also with the Airtable front end (ticket 13), which replaces the page, not the `decide` command.*
- [x] On merge, accepted events carry `reviewer`, `review_date`, `status = accepted`; rejected ones carry `status = rejected` and stay in the files for the agreement report (ticket 10).
- [x] The validator blocks merge when any accepted event lacks a source or a move. *Also: a rejected event needs a note; a project-coded move needs its intensification criterion.*
- [x] Seam-1 test: a fixture PR reviewed with each decision type yields the expected file state.
