# 46 — Move sequences: does one claimant's move draw the other's? (exploration)

Asked by the maintainer on 2026-11-27, when episodes (ticket 45) came off the site: try the same question from
the moves, which MATS codes evenly from 1970 to 2026, instead of from the event layer.

## The question, put to the data

A move by A directed at B is *followed* when B makes a move directed at A in one of the next two years
(MATS is annual, so moves of the same year cannot be put in order; they are counted apart), in a sub-region
the first move covers. The rate of following is compared with chance: the same check made for a two-year
window placed at random over 1970–2026. Scripts: `explore/sequences.py`, `explore/lags.py` (kept outside the
repository; the figures below are from main on 2026-11-27).

| Directed pair | Moves | Followed | Rate | Chance |
|---|---|---|---|---|
| Philippines → China | 129 | 117 | 0.91 | 0.91 |
| China → Vietnam | 121 | 89 | 0.74 | 0.71 |
| Vietnam → China | 116 | 91 | 0.78 | 0.73 |
| China → Philippines | 110 | 86 | 0.78 | 0.82 |
| China → Malaysia | 59 | 41 | 0.69 | 0.53 |
| Vietnam → Philippines | 42 | 35 | 0.83 | 0.60 |
| Indonesia → China | 28 | 20 | 0.71 | 0.58 |

## What it shows

- For the pairs with most moves the rate is what chance gives: China, the Philippines and Vietnam make moves
  toward one another in almost every year and sub-region, so nearly any move is "followed" whatever the
  link between them.
- Year on year, the two sides of a pair step up in the same years (correlation of their yearly scores 0.3 to
  0.5 for China with the Philippines, Vietnam, Malaysia and Indonesia), but neither side's year says much about
  the other's next year once the other's own record is known (partial correlations under 0.2, short of what
  56 years would need).
- The follow-up's type is as often lower as higher: no sign of matching or out-escalating.
- Place: only a few moves can be tied to the same feature on both sides (21 for the Philippines toward China).

So at the resolution MATS works at (a year, a sub-region) the data show *that* two claimants step up together,
not *who answers whom*. An action-and-reaction view would claim more than they hold; the Over time tab of a
pair page already shows the two directions year by year.

## Possible

- Nothing more (the recommendation).
- A modest note on a pair page's Over time tab: the years in which both sides made moves toward each other.
