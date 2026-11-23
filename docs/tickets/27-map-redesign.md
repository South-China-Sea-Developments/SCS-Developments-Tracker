# 27 — The assertiveness map, first version

Brief: `docs/notes/map-brief.md`. Agreed with the maintainer on 2026-11-22; a first version to react to,
then several rounds of tuning over the following weeks.

## What a visitor sees

- **First screen:** the site banner (a slim strip on this page only, about 120–150 px) and the menu, then
  one map filling the rest of the screen: the ten sub-regions shaded by assertiveness in the **latest
  five-year window**, which ends at the build year (2022–2026 in 2026) even while those years are still
  being reviewed. Nothing else competes with it.
- **On scrolling:** the map stays put and a panel slides up over it with the controls and the detail:
  - a year slider that moves the five-year window from 1970–74 to the latest, with a play button;
  - a claimant selector (all claimants by default);
  - a details panel for the sub-region clicked or chosen: its score, its moves (linked to their case
    pages) and how many are coercive or force;
  - the event points, an optional layer, off by default, drawn in neutral ink so they explain the colour
    rather than compete with it;
  - one line under the slider on the coding source: Chubb's coding for China, Vietnam and the
    Philippines to 2015, the project's own after; Malaysia, Indonesia and Taiwan project-coded throughout.
- **Further down:** the existing tracker (filters, event map, events in view), unchanged.

## The measure

- A move counts in a window when its year falls in it, and on every sub-region it is flagged for.
- Its weight is its highest type: declarative 1, demonstrative 2, coercive 3, force 4.
- A sub-region's score in a window is the sum of the weights of the moves on it; with a claimant
  selected, only that claimant's moves.
- The colour scale is fixed across all windows for the current claimant selection (its maximum over
  every window), so a darker shade in one window than in another means more, or harsher, moves.
  The ramp is read on a square-root scale (score ÷ maximum, square-rooted), so lower scores stay
  legible beside the peak windows; the order is unchanged.
- One sequential ramp (the site's `--seq` blues, which the type pills already use: declarative light,
  force dark); a score of 0 is unfilled. Legend: lighter = less, darker = more and harsher.

## Round 2 (maintainer, 2026-11-22)

- **Precision:** each sub-region carries its number of moves in the window; zoomed in, or with a
  sub-region chosen, the reefs, shoals and islands the moves' descriptions name appear (gazetteer match,
  `gazetteer.named_features`; about a third of moves name one), each with its moves. The events layer
  is gone from this map.
- **One map on the home page:** the event tracker (filters, event map, events in view) moves to
  `map.html`, "Events" in the menu.
- **Banner, a proposal:** no banner above the home map; the institute's logo in the menu band (cropped
  from the banner; an official logo file would be better), the full banner after the map. Other pages
  keep the banner on top.
- **Phone:** the map sticks to the top half and the panel scrolls beneath it instead of over it.

## Round 3 (maintainer, 2026-11-22)

- No banner on the home page at all (every other page keeps it on top); the site is named "South China
  Sea Developments Tracker" wherever it showed "SCS Developments Tracker".
- The map opens on the latest five years that have moves in them (2016–2020 today), so it advances by
  itself as the recent years are reviewed; the slider still reaches the build year. This replaces the
  first round's opening on 2022–2026.
- The legend reads "Degree of assertiveness", Low to High.

## Round 4 (maintainer, 2026-11-22: "do all of them to try"; colour more discreet)

- **Change:** ▲/▼ beside a sub-region's number when its score rose or fell by a fifth or more (and by at
  least one point) against the five years before; "Rising since …" in the details.
- **Features:** spot check of 12 matches: 10 right, 2 passing mentions (a commemoration naming Taiping
  Island, a PR campaign about Johnson South Reef). Five spelling variants added to the gazetteer (143
  moves now place, from 140); the larger extension needs Wikidata, next session.
- **Key moments** on the slider (1974, 1988, 1995, 2012, 2014, 2016; each opens the window ending two
  years after) and a tick where Chubb's coding ends.
- **Address:** `#y2015-cn-s6-f-scarborough-shoal` (window end, claimant, sub-region, feature), kept up to
  date as the view changes, read on load; "Copy a link to this view".
- **By decade:** six small maps (1970s–2020s, decade sums on their own fixed scale); a click opens the
  decade's last window.
- **Weighting:** a switch, on by default, shares each move's weight among the sub-regions it covers
  (`window_scores(shared=True)`); off counts it in full on each.
- **Finishing:** fills at 55 % far out (22 % zoomed in or with a sub-region chosen), white hairline seams,
  lighter count pills; feature names from zoom 7 or on hover; visible keyboard focus on every marker.
  An official ASPI logo file would replace the crop.

## Round 5 (maintainer, 2026-11-22)

- Key moments removed (the tick where Chubb's coding ends stays).
- Decade maps made quieter: smaller, paler, an underline for the current decade, a plain label.
- A switch between the **five-year window** (default) and the **build-up since 1970**, as MAVD's map
  accumulates (`cumulative_scores`); the build-up has no arrows, since it only grows. In the address as `-c`.

## Round 6 (maintainer, 2026-11-22: borrowed from MAVD and ACLED's East Asia Maritime Monitor)

- **Timeline** above the slider: moves per year, stacked by type, the years on the map highlighted; a
  click on a year moves the window there. It follows the filters and the sub-region chosen.
- **Type filter** (four toggles, at least one stays on) and **directed at** (the dyads' targets) beside
  the claimant. The page now computes every score from the moves so the filters recombine them;
  `window_scores` stays as the reference, and a site test holds the page's scores to it. The precomputed
  score sets (shared, cumulative, decades) left the payload.
- Reference lines (maintainer, round 7): "Maritime boundaries (indicative)" and "China's dashed line (a
  claim)", both off by default, from Natural Earth (public domain; `web/static/geo/`). Natural Earth's
  maritime lines are indicative median, treaty and disputed lines between neighbours, sparse inside the
  sea, not 200-nm EEZ limits; a full EEZ layer needs the Marine Regions data (CC BY), which the
  maintainer would have to supply.
- Round 8: a gentle zoom in (up to 0.6 levels, halfway down the section) and back out as the page scrolls past the map, on the whole-sea view only, off once the reader zooms, pans or picks a sub-region, and off under reduced motion.
- Round 7 also: the coding-source note under the slider removed (the tick's tooltip keeps it); the
  "Most intense" line removed from the details.

## Later rounds (not in this ticket)

Small multiples by decade; a per-claimant timeline; a fuller marking of the coding-source change; the
banner fading into the map; weighting and normalisation tuning (by window length, sea-wide claims).

## Tests

- The window scores (`web.build.window_scores`): weight by highest type, sum per sub-region, claimant
  filter, window bounds, the fixed maximum, the latest window ending at the build year.
- The tracker page carries the hero map, the controls and the scores; the existing tracker is still there.
- The rendered page is checked by eye at laptop and phone widths before the preview goes out.

Ships on a branch with a private preview; merged only when the maintainer approves.
