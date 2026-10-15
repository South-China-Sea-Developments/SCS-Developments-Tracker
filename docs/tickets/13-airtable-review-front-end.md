# 13: Airtable review front end

**What to build:** A coder who prefers Airtable reviews the same candidates there and their decisions land in the pull request exactly as if made on the review page.

**Blocked by:** 06

**Status:** ready

- [ ] Candidates of an open PR are mirrored into an Airtable base with the same fields and decision options.
- [ ] Decisions made in Airtable are written back to the PR as commits; Airtable is never read by the loader, validator or site build.
- [ ] Seam-1 test: the same fixture PR reviewed via Airtable and via the review page yields identical files.
- [ ] The sync can be disabled by configuration with no effect on the rest of the system.
