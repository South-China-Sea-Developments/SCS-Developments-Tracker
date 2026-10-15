# 04: Issues/Domains and Sub-regions pages

**What to build:** The remaining MAVD views exist on the site: moves by Issue and by Domain over time, and the sub-region choropleth in five-year bins over the ten polygons.

**Blocked by:** 02

**Status:** done (2026-10-15, PR #4)

- [x] Issues/Domains page reproduces the MAVD charts (by claimant, by year) from the files. *Deliberate change of form:* MAVD shows issue and domain mix as 100 % stacks and the by-location charts as grouped bars; this site shows absolute counts as stacked columns, which keeps the mention/move distinction visible. A share view can be added later if readers ask for it.
- [x] Sub-regions page: choropleth of the ten polygons with a claimant selector and five-year bins (1970, 1971–75, … 2011–15, extending automatically as years are added); hovering a polygon shows its counts. *(Moves by sub-region stacked by type corresponds to MAVD's "Assertive Moves by Subregion"; MAVD's ten-series "Locations of assertive moves" by year is replaced by one small chart per sub-region, since ten colours cannot be told apart.)*
- [x] Counts on both pages equal the validator's independent aggregates.
- [x] Headless render test passes.
