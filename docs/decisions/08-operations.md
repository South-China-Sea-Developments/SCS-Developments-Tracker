# 08. Operations

**Depends on:** 04, 05.

**Question.** Where scheduled runs execute, what they cost, who is notified, who maintains, how failures surface.

**Settled 2026-10-15 (ticket 07):** Scheduled runs execute on **GitHub Actions** in this repository (`.github/workflows/harvest.yml`), every Monday at 06:17 UTC and on demand. The run restores the harvest state, fetches the active sources, extracts candidates, opens the review pull request, saves the state and posts reminders. The only running cost is the extractor's API calls, paid through the `ANTHROPIC_API_KEY` repository secret; each run's tokens, estimated cost and yield are appended to a run log so the cost is known per run and in total.

**Harvest state** (which items each source has already yielded) lives on a dedicated **`harvest-state` branch** that is never merged: `state.json` plus `runs.jsonl`. A dedicated branch rather than the review pull request, because a pull request can stay open for weeks and the next run must still start where the last one stopped; rather than a direct commit to `main`, because nothing lands on `main` without a pull request (ADR 0004), and the state is operational, not data. A failed run does not save its state, so the next run retries the same items.

**Notification:** a failed run opens one issue labelled `harvest-failure` with the run summary and a link to the log; further failures comment on that issue instead of opening another; the next successful run comments and closes it. A review pull request open for more than seven days gets a comment mentioning the maintainer, at most once a week. The maintainer is named in the workflow (`MAINTAINER`), one line to change on handover.

**Maintainer:** Angelo M. (`Angelo-M-SCS`). Ongoing duties: review pull requests, add or retire sources in `pipeline/sources.json`, keep the secret valid, act on failure issues.

**Dry run:** `workflow_dispatch` with `dry_run` fetches the live sources but extracts the fixture captures with the recorded responses, opens no pull request, saves no state and posts nothing, so the wiring can be checked at no extractor cost.
