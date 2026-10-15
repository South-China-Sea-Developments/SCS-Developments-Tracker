# 06. Public front end

**Depends on:** 05.

**Question.** Reproduce MAVD's layout, or build a new map + charts + case browser; which features; where hosted?

**Settled 2026-10-15:** MAVD-equivalent views (so the 1970–2015 comparison holds and doubles as a data-loading check) **plus an event layer**: real event points with time filtering, per-claimant timelines distinguishing moves from their events, filters by Type/Domain/Issue/Dyad, a case browser with sources as links, and a Downloads page with CSV, GeoJSON and a citation at a tagged version.

Visual style is free (need not resemble MAVD); the requirement is clear, clean, comprehensive, well organised. The site will later be hosted on the ASPI website, so it is built as a **portable static bundle** (relative paths, no dependency on GitHub Pages features) that can be dropped onto any web host; GitHub Pages is the interim host.
