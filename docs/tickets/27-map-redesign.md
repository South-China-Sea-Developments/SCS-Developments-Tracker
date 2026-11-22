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

## Later rounds (not in this ticket)

Small multiples by decade; a per-claimant timeline; a fuller marking of the coding-source change; the
banner fading into the map; weighting and normalisation tuning (by window length, sea-wide claims).

## Tests

- The window scores (`web.build.window_scores`): weight by highest type, sum per sub-region, claimant
  filter, window bounds, the fixed maximum, the latest window ending at the build year.
- The tracker page carries the hero map, the controls and the scores; the existing tracker is still there.
- The rendered page is checked by eye at laptop and phone widths before the preview goes out.

Ships on a branch with a private preview; merged only when the maintainer approves.
