# 08: Event map with time slider and filters

**What to build:** A visitor sees real event locations on a map, scrubs through time, and filters by claimant, Type, Domain, Issue and Dyad; named features resolve to coordinates from a committed gazetteer.

**Blocked by:** 03, 06

**Status:** ready

- [ ] A committed gazetteer of South China Sea features (reefs, banks, islands, shoals; English, Chinese, Vietnamese, Filipino names) with coordinates and sub-region.
- [ ] Events with `location_precision = point` or `feature` are plotted; `subregion`-only events are shown as sub-region counts, not points.
- [ ] Time slider by year and month; filters as listed; clicking a point opens the event and its move.
- [ ] Map works offline from the bundle except for the basemap tiles, which come from a free, attribution-compliant provider.
- [ ] Headless render test passes; event counts on the map equal the validator's.
