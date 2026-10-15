# 0001. Keep the MATS 1.0 coding scheme; extend it additively only

Date: 2026-10-15. Status: accepted.

## Context

The project continues Chubb's Maritime Assertiveness Time Series (MATS 1.0, 1970–2015, 357 moves) to the present and builds an automatically updated public database on top of it. The existing series is published, cited, and backed by a methodology appendix. The new data must cover 2016 onward and should carry information MATS lacks (exact dates, locations, structured sources, possibly further claimants).

## Decision

The MATS 1.0 variables — Type (Declarative / Demonstrative / Coercive / Force), Domain, Issue, Sub-region, Dyad, Ongoing-through — keep their definitions and their 1970–2015 values unchanged. Chubb's methodology appendix is the codebook for these variables, for old and new years alike.

Everything new is **additive**: new columns or new tables that attach to a move without altering any existing column. Existing values are corrected only on evidence of error, with the correction recorded.

## Alternatives considered

- **Adopt the scheme with no additions.** Rejected: dates, coordinates and structured sources are the main gaps users of the data have, and they do not threaten comparability.
- **Redesign the scheme** (grey-zone categories, coast guard / militia actor types, finer intensity scale). Rejected: it would require re-coding all 357 moves before any new year could be added, and the result would no longer be comparable with the published analyses the author's permission was granted for.

## Consequences

- The 1970–2015 series remains directly comparable with Chubb (2021, 2022); charts reproduced from MAVD must match the published counts.
- Any new analytic category (e.g. actor sub-type) is added as a separate variable, never by splitting or re-defining a MATS variable.
- Changing a MATS variable's definition later requires a new ADR and a re-coding plan.
