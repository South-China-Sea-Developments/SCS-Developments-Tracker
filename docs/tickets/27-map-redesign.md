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

## Later rounds (not in this ticket)

Small multiples by decade; a per-claimant timeline; a fuller marking of the coding-source change; the
banner fading into the map; weighting and normalisation tuning (by window length, sea-wide claims).

## Tests

- The window scores (`web.build.window_scores`): weight by highest type, sum per sub-region, claimant
  filter, window bounds, the fixed maximum, the latest window ending at the build year.
- The tracker page carries the hero map, the controls and the scores; the existing tracker is still there.
- The rendered page is checked by eye at laptop and phone widths before the preview goes out.

Ships on a branch with a private preview; merged only when the maintainer approves.
