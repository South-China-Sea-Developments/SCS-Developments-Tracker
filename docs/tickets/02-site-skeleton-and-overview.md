# 02: Site skeleton with the MAVD-equivalent overview

**What to build:** A visitor opens the published site and sees the overview: assertive moves by claimant and year, split by Type, for 1970–2015, with a methodology/credits page naming Chubb and the sources. The numbers on screen are the numbers in the files.

**Blocked by:** 01

**Status:** done (2026-10-15, PR #2)

- [x] A build command produces a self-contained static bundle from the canonical files (relative paths only; no host-specific features).
- [x] Overview page: moves per claimant per year as the MAVD chart types (total and by Type), plus a six-claimant selector that gracefully shows empty series for MY/ID/TW. *(The all-claimants chart stacks by claimant or, as in MAVD, by type; empty claimants show a plain message and no table toggle.)*
- [x] Methodology and credits page: project description, Chubb's citation block, link to the codebook sources, data version and build date.
- [x] The build emits aggregate JSON; a test asserts those aggregates equal aggregates computed independently by the validator.
- [x] Headless-browser test: every page renders with no console errors.
- [x] On merge to `main`, CI rebuilds and publishes to GitHub Pages; the URL is in the README. *(Pages must be switched to the "GitHub Actions" source once in repository settings; the API does not allow doing it from here.)*
- [x] Visual style is new (not MAVD's); clear, clean, well organised; legible on a phone.
