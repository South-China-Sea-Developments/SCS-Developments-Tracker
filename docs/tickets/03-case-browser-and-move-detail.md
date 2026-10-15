# 03: Case browser and move detail

**What to build:** A visitor searches and filters the list of moves and opens any move to read its description, full coding, events and sources.

**Blocked by:** 02

**Status:** done (2026-10-15, PR #3)

- [x] List page with free-text search over description and filters by claimant, year range, Type, Domain, Issue, Dyad, Sub-region; counts update with filters.
- [x] Detail page per move: description, all MATS variables rendered with their labels, Ongoing-through, dyads, sub-regions on a small inset map, events in date order with their sources as links, provenance (coded_by, data version), and `pending` status shown where applicable.
- [x] Deep links: each move has a stable URL within the bundle.
- [x] Headless render test over a sample of moves; aggregates unchanged.
