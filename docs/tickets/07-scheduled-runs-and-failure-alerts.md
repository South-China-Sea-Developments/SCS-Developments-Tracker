# 07: Scheduled runs and failure alerts

**What to build:** The harvest runs weekly without anyone starting it, the site rebuilds on every merge, a failed run opens an issue, and a review PR that waits more than a week triggers a reminder.

**Blocked by:** 06

**Status:** ready

- [ ] Weekly scheduled CI job runs the harvester and opens the PR; secrets (extractor API key) are repository secrets, never in files.
- [ ] Site rebuild and publish on every merge to `main`.
- [ ] A failed run opens a GitHub issue with the log; repeated failures do not open duplicates.
- [ ] A review PR older than seven days triggers a reminder to the maintainer.
- [ ] A dry-run mode exists for testing the workflow without consuming extractor budget.
