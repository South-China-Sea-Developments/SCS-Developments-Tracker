# 03. Claimant scope

**Depends on:** 01. **Blocks:** 04 (volume of backfill).

**Question.** Code only China, Vietnam and the Philippines (as MATS), add Malaysia, Indonesia and Taiwan from 2016 only, or add them with a full 1970–2015 backfill?

**Settled 2026-10-15:** add Malaysia, Indonesia and Taiwan **with a full 1970–2015 backfill**, so all six claimants have comparable series. Chosen for completeness; the project has no fixed timeline yet and is exploratory. Brunei remains a dyad target only unless later decided otherwise (it was: see the amendment of 2026-11-23 below).

**Consequences.**
- Moves for MY, ID and TW in 1970–2015 are this project's own coding, not Chubb's. Every move carries a `coded_by` / `data_version` so the two provenances never mix; comparability tests against the published series apply to CN, VN and PH only.
- Chubb's year-on-year intensification rule and 1970 baseline apply to the new claimants exactly as to the original three, which means a baseline list of pre-1970 actions is needed for each.
- Workload roughly doubles relative to the three-claimant option; the pipeline and coding routine should be proven on CN/VN/PH 2016+ first, then applied to the new claimants.
- *2026-10-19 (ticket 11):* the order in the last point was reversed in practice — the live harvest of CN/VN/PH 2016+ waits for the API key, so the first candidates through the review queue are hand-compiled MY/ID/TW events (2016–2026). The first CN/VN/PH 2016+ review remains the check that the routine reproduces Chubb's coding before the backfill (ticket 12) starts.
- *Amended 2026-11-23 (ticket 42):* **Brunei is added as a seventh claimant (BN), with a series from 1970 like the others.** Until 1 January 1984 the United Kingdom conducted Brunei's foreign affairs while the Sultanate ran its own internal government and oil licensing; acts of the Sultanate's government count as Brunei's moves from 1970, and acts of the British Crown for Brunei (the 1954 and 1958 Orders in Council on its boundaries and continental shelf) are listed in the baseline as colonial context, as Sarawak and North Borneo are for Malaysia. The maintainer chose this to keep all seven series comparable. Brunei's moves are this project's own coding (`coded_by` project); MATS never coded Brunei as an actor, only as a dyad target (letter B).
