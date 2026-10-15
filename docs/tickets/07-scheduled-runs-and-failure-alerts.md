# 07: Scheduled runs and failure alerts

**What to build:** The harvest runs weekly without anyone starting it, the site rebuilds on every merge, a failed run opens an issue, and a review PR that waits more than a week triggers a reminder.

**Blocked by:** 06

**Status:** done (2026-10-15, PR #7)

- [x] Weekly scheduled CI job runs the harvester and opens the PR; secrets (extractor API key) are repository secrets, never in files. *`.github/workflows/harvest.yml`, Mondays 06:17 UTC and on demand (replaces the manual workflow; its `since`/`only`/`model` inputs remain). Harvest state travels on the `harvest-state` branch (decision 08) with a per-run log of cost and yield; a failed run leaves the state untouched, and documents whose extraction failed are retried next run. A pull request opened with `GITHUB_TOKEN` does not trigger the validate workflow until a person pushes to it; a fine-grained `HARVEST_TOKEN` secret (contents + pull requests: write) removes that limitation. First live run still waits for `ANTHROPIC_API_KEY`.*
- [x] Site rebuild and publish on every merge to `main`. *`pages.yml`, in place since ticket 02.*
- [x] A failed run opens a GitHub issue with the log; repeated failures do not open duplicates. *`pipeline.ops failure-issue`: one open issue labelled `harvest-failure` holds the run summary and log link; later failures comment on it; the next success closes it.*
- [x] A review PR older than seven days triggers a reminder to the maintainer. *`pipeline.ops remind`: a comment mentioning `MAINTAINER` on every open `harvest/*` pull request older than seven days, at most once per seven days.*
- [x] A dry-run mode exists for testing the workflow without consuming extractor budget. *`dry_run` input: live fetch, fixture captures through the recorded extractor, `queue open --no-push` (branch and commit, no push), no state push; the failure-issue and reminder steps read GitHub and print their writes. Not exercised by a dry run: branch push, pull request creation, state push — the first real run shows those.*

Tests: `tests/test_ops.py` (failure-issue and reminder logic against a hand-written GitHub fake; `gh api` argument handling; the state branch round trip, remote-error and stale-branch cases against a local bare remote with depth-1 clones as in CI; `harvest run` stopping after a failed fetch). The workflow file is verified by a dispatched dry run after merge; its link is recorded here once run.
