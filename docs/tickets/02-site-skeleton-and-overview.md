# 02: Site skeleton with the MAVD-equivalent overview

**What to build:** A visitor opens the published site and sees the overview: assertive moves by claimant and year, split by Type, for 1970–2015, with a methodology/credits page naming Chubb and the sources. The numbers on screen are the numbers in the files.

**Blocked by:** 01

**Status:** ready

- [ ] A build command produces a self-contained static bundle from the canonical files (relative paths only; no host-specific features).
- [ ] Overview page: moves per claimant per year as the MAVD chart types (total and by Type), plus a six-claimant selector that gracefully shows empty series for MY/ID/TW.
- [ ] Methodology and credits page: project description, Chubb's citation block, link to the codebook sources, data version and build date.
- [ ] The build emits aggregate JSON; a test asserts those aggregates equal aggregates computed independently by the validator.
- [ ] Headless-browser test: every page renders with no console errors.
- [ ] On merge to `main`, CI rebuilds and publishes to GitHub Pages; the URL is in the README.
- [ ] Visual style is new (not MAVD's); clear, clean, well organised; legible on a phone.
