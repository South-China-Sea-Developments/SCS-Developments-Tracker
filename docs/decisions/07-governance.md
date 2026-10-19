# 07. Governance

**Depends on:** 01.

**Question.** Data licence, dataset name and versioning (relationship to "MATS 1.0"), citation format, the author's role (credited, consulted, collaborator), update cadence and release policy.

**Settled in part 2026-10-16 (ticket 09):** the dataset is named *SCS Developments Tracker* and numbered as a continuation of MATS: 1.x is Chubb's, this project's versions are 2.x (`DATASET_VERSION`, written on every project-coded move), `MAJOR.MINOR.PATCH` with MAJOR for a change to the scheme or unit (none planned), MINOR for new coverage, PATCH for corrections; a `-dev` suffix while the dataset is being built. A release is a tag on `main`; the GitHub Release and the site's Downloads page serve the files as they are at the tag with checksums; one `CHANGELOG.md` section per tag. The citation names the project and the maintainer and is always given together with Chubb's own citations, including his suggested dataset citation in his words (version 1.01, May 18); `CITATION.cff` carries it machine-readably.

**Still open:** the data licence (nothing is stated until the author agrees; all rights remain with their authors), the author's preferred credit line and role, and the code licence. Until these are settled the Downloads page says so and no licence file exists.

**Added 2026-10-19 (maintainer's instruction):** No project-coded entry is merged into the dataset until the maintainer has reviewed it himself on its review page; no further candidate sets are compiled or queued until he asks for them. Review PR #17 stays open for his decisions.
