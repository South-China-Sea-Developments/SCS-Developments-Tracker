# 0002. Two-level unit of analysis: Move and Event

Date: 2026-10-15. Status: accepted.

## Context

MATS codes one *move* per claimant per year (a single action or a closely linked series). Automated harvesting from news and official statements yields single dated incidents, one at a time. Something has to bridge the two, and the choice fixes the shape of every table, the review workflow and the public site.

## Decision

Two levels, linked:

- **Move** stays the MATS unit and carries all MATS variables (Type, Domain, Issue, Sub-region, Dyad, Ongoing-through) exactly as in ADR 0001. Yearly counts and all comparisons with the 1970–2015 series are made at this level.
- **Event** is a single dated, located, sourced incident. Each event belongs to exactly one move; a move groups one or more events. Dates, coordinates and sources live on events.

For 2016 onward, the pipeline harvests events; a coder groups them into moves and codes the move. For 1970–2015, events are backfilled gradually from the move descriptions and the online `Dates` column; a move with no backfilled events is still complete at move level.

## Alternatives considered

- **Move only, with date and coordinate columns added to the move.** Rejected: a multi-incident move has no single date or place, so the added columns would be approximate and the harvested detail would be thrown away.
- **Event only going forward.** Rejected: counts would jump by an order of magnitude after 2015, breaking the series, and MATS variables are defined for moves, not incidents.

## Consequences

- The canonical data has (at least) two tables: moves and events, plus a sources table attached to events.
- The review workflow has a grouping step (which events form a move) before the coding step.
- The public map can show real event locations where known, replacing MAVD's synthetic points; sub-region remains the move-level location.
- Comparability tests check move counts per claimant-year against the published series.
