# 09. Series start

**Depends on:** 01, 03. **Blocks:** nothing.

**Question.** Keep 1970 as the first coded year for all six claimants, as in MATS, or extend the series back to 1949 (the PRC's founding) or 1946 (the common zero: Japan's surrender, the ROC recovery operation, Philippine independence, the French return to Indochina)?

**Settled 2026-11-17:** **keep 1970.** The pre-1970 record stays where it is — the baseline lists in `data/baselines/`, one per claimant, against which each claimant's 1970 is judged (Chubb's own list for the PRC, the project's for the other five).

**Why.** Chubb's reason for 1970 holds for all six: the ECAFE survey had just raised the stakes for every claimant at once, and the year-on-year method needs a stretch of years with usable sources on both sides of each comparison. 1946–69 is where the present-centric bias is worst — thin years, secondary chronologies, several claimants with nothing for a decade — and the baseline compilation already found its limit there (43 unverified leads across five claimants). Coding 1969 in full would also create a seam at 1970 that cannot be resolved: some of Chubb's 1970 novelties might show 1969 precedents, and his rows do not change (ADR 0001). Actor continuity before 1970 (mainland ROC → Taiwan; State of Vietnam → RVN beside the DRV; colonial Borneo → Malaysia; US-era → independent Philippines) would need decisions of its own. The extension would strengthen the dataset's account of continuity but add little to a developments tracker whose readers follow the present; it would cost about twelve chunks at the pre-2000 rate.

**Consequences.**
- The site's charts and the comparability test are unchanged; the baselines ship with every release and are read before a claimant's 1970s are reviewed (`docs/coding-guide.md`, step A).
- Reopening this later is a new decision, not a reversal: the natural start would be 1946, not 1949; the first step would be to ask the author for the pre-1970 part of his master timeline, which "was not restricted to the post-1970 era" (appendix, Stage 1); and it would come after the first full review cycle has shown what the schema needs.
