# 44 — Between claimants: how claimants direct their moves at one another

Asked by the maintainer on 2026-11-27 and designed with him over eight rounds of mock-ups (the "SCS
Tracker: dyad dynamics mock" canvas). The aim: to see the tendency of how each claimant presses the
others, toward whom it is more or less confrontational, where, how coercively, and for how long. Not who
"leads" or "wins": the page describes tendencies and never ranks a winner.

## What the reader gets

- **A page of its own, "Between claimants"**, in the site menu, built like the homepage: the dark side
  panel and a full map. Calm on arrival; the rest of the toolkit one level down.
- **Opening view, all claimants**: on the map a line joins each pair of claimants. Its width and shade
  are the pair's score for the five-year window (both directions together). ▲ ▼ mark a change of a fifth
  or more against the five years before. A corner card lists the five highest scores, each with its count
  of moves and its share coded coercive or force. Pairs with no moves in the window are not drawn.
- **One claimant chosen**: the lines become arrows from that claimant to each other claimant (a switch
  turns them round: the others' moves toward it). Beside the map, round 3's two lists: the claimant's
  moves toward each other claimant, and each one's moves toward it, each with a bar by type.
- **A pair chosen**: its own page, `between-claimants/<a>-<b>.html` (for example
  `between-claimants/china-vietnam.html`), linkable and citable. The map shades the ten sub-regions by
  the pair's score in the window; each shows its number of moves and an arrow for a change. Switches:
  direction (both, or one side), coercive and force only, and counting each move in full on every
  sub-region. The side panel has the pair's score, count and share, and a bar by type for each direction.
  Tabs under the map: Over time (the mirrored timeline, the window highlighted), For how long (moves in
  force each year), Where (the ten sub-regions ranked, both directions, mix by type, share), The moves
  (the window's moves, linked to their case pages), About the data.
- **Every pair, in numbers**: round 3's full table (count, mix by type, share), collapsed under the map.
- **Tools as on the homepage**: copy a link to the view, cite, embed.

## The measures (the same as the homepage's, so the two pages speak one language)

- **Window**: five years, sliding, ending at the build year by default; a play button; an "all years"
  switch for 1970 to the build year.
- **Score**: each move weighted by its highest type, declarative 1, demonstrative 2, coercive 3, force 4,
  on the homepage's blue ramp and on a scale fixed across every window (square-root, as there).
- **Sub-regions**: by default a move's weight is shared among the sub-regions it covers, as on the
  homepage, with the same switch to count it in full.
- **Who a move bears on**: its dyads. A move counts for a pair when one claimant's dyad names the other
  (`CV`: China toward Vietnam).
- **Moves aimed at all claimants** (dyad `xA`): counted in the tables and lists, drawn as a grey part of
  a bar with a "+" figure; left out of the coercive share and never drawn on a map.
- **Share coded coercive or force**: the coercive and force moves among those aimed at the other claimant.
  **Under 10 moves no share is given**, only "few moves".
- **China and Taiwan**: drawn dashed and grey and left out of rankings; Beijing treats Taipei's claim as
  China's own, so the pair is not read like the others.
- **Durations**: a move is in force from its year to its `ongoing_through` year. A dashed upper bound
  counts every move whose end has not been re-checked as still running.

## Wording

Neutral and hedged (the maintainer, 2026-11-27): "moves directed at", "recorded moves", "coded as
coercive or force", "pairs with the highest scores"; never "challenged", "confronted", "most aggressive"
or "won". The four type names are Chubb's categories and stay.

## About the data, on every pair page

Who coded which years (Chubb's MATS 1.02 for 1970–2015; the project since, with his rules), the
languages of the sources behind the pair's events, and one line on the method: a move marks a step up
against the year before, so a standoff held at the same level shows in how long a move lasts rather than
in new moves.

## Later (not in this ticket)

- **Episodes** in the Events tracker (the maintainer, 2026-11-27): events by opposite sides at the same
  place within six months, proposed by the pipeline and confirmed, named or rejected by the maintainer in
  Airtable; the pair pages then gain an Episodes tab linking to them.
- **Outside powers**: moves directed at the United States (dyad `xU`) and others, as a later layer.
- **Download the map as an image**, as the homepage offers.
- Fine-tuning on the live site.

## Tests

- The page and all 21 pair pages build, linked from the menu.
- The pair counts and shares the page carries equal an independent count from `moves.csv`.
- In a browser: the opening view draws a line per pair with moves in the window; choosing a claimant
  draws arrows; a pair page shades the sub-regions and its tabs open, with no console errors.
