# 03. Claimant scope

**Depends on:** 01. **Blocks:** 04 (volume of backfill).

**Question.** Code only China, Vietnam and the Philippines (as MATS), add Malaysia, Indonesia and Taiwan from 2016 only, or add them with a full 1970–2015 backfill?

**Settled 2026-10-15:** add Malaysia, Indonesia and Taiwan **with a full 1970–2015 backfill**, so all six claimants have comparable series. Chosen for completeness; the project has no fixed timeline yet and is exploratory. Brunei remains a dyad target only unless later decided otherwise.

**Consequences.**
- Moves for MY, ID and TW in 1970–2015 are this project's own coding, not Chubb's. Every move carries a `coded_by` / `data_version` so the two provenances never mix; comparability tests against the published series apply to CN, VN and PH only.
- Chubb's year-on-year intensification rule and 1970 baseline apply to the new claimants exactly as to the original three, which means a baseline list of pre-1970 actions is needed for each.
- Workload roughly doubles relative to the three-claimant option; the pipeline and coding routine should be proven on CN/VN/PH 2016+ first, then applied to the new claimants.
