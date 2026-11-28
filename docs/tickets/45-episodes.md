# 45 — Episodes: following an exchange between two claimants from start to finish

Asked by the maintainer on 2026-11-27, after Between claimants (ticket 44), where the idea first appeared
as "threads"; he prefers *episodes*. An episode is a run of events by two claimants at the same place, each
within six months of the last. It shows a sequence, never a claim that one act caused another.

## Decided

- **The pipeline proposes, the maintainer confirms** (2026-11-27): episodes are found automatically and go
  to the base's Episodes table, where he confirms (and names) or rejects each one; only his answers reach
  `data/episodes.csv` and the site (ADR 0003).
- **The rule**: two accepted events are linked when they belong to claimants whose moves are directed at
  each other (a move's dyads name the other claimant), lie within 25 km of each other and within 180 days;
  an episode is a chain of links with events by both claimants. Only events with coordinates and a day or
  month date take part. On 2026-11-27 this gave 15 episodes (78 events): 10 China–Philippines, 2
  China–Vietnam, 2 China–Malaysia, 1 Malaysia–Vietnam; 10, 25 or 50 km change the count by one at most.
- **Where they live on the site**: the Events page (an Episodes view beside the events), each episode
  followed on the map from start to finish; the pair pages of Between claimants gain an Episodes tab.
  Design in rounds on the canvas, as for ticket 44 (round 1: 2026-11-27).

## Built

- `pipeline/episodes.py`: `find`, `proposals` (new, or *extend* for a decided episode with events found
  since), `rows` (the Airtable records), `apply` (his answers into `data/episodes.csv`, archived under
  `harvest/airtable/episodes/`), `check` (run by the validator).
- The Episodes table in the base (`tblgnx0ydOXJsJskT`), its field ids in `pipeline/airtable.json`; the first
  15 proposals pushed on 2026-11-27.
- The weekly task: step A4 applies his answers and merges them once CI passes (decision 07); step C9
  proposes new episodes; the base's room count includes the table.

- The site (2026-11-27, after design round 2 on the canvas): the Events page has two views, Events and
  Episodes (`episodes.html`: the confirmed episodes in a list, each a numbered ring in its two claimants'
  colours on the map, rings at the same feature side by side, a pair filter); each confirmed episode has its
  own page (`episodes/<name>.html`): its events in two columns, one per claimant, a map with one marker per
  place (events within 3 km share one; its ring split by claimant) and a strip below with one row per
  claimant, and Play to light the events in order. The pair pages of Between claimants have an Episodes
  tab; the methodology page has an Episodes section; `data/episodes.json` holds what the pages show.
  Round 1 drew the events as bubbles fanned around a single point; the maintainer found it odd, so the
  map shows where and the strip shows when.

## Taken off the public site (2026-11-27)

The maintainer, on seeing the 15 proposals: fifteen episodes in 56 years reads as if only fifteen had happened,
and an incident catalogue goes against the spirit of MATS, which observes steps up in assertiveness rather
than tracking every item. All fifteen were from 2016 on: episodes come from the event layer, which has
precise dates and positions mostly from then, so their number measures the data's density, not the sea.

- The Episodes view, the episode pages, the pair-page tab and the methodology section are no longer built
  for the site (`EPISODES_ON_SITE = False` in `web/build.py`); `python -m web.build --episodes` still builds
  them for internal use, and the tests cover both.
- The weekly task no longer applies answers (A4) or proposes episodes (C9); the 15 proposals were cleared
  from the base's Episodes table, which is kept, empty. `pipeline/episodes.py` and the validator's check of
  `data/episodes.csv` (absent) stay.
- Next: ticket 46 explores the same question from the moves, which cover 1970–2026 evenly: a move by one
  claimant followed, at the same place, by a move of the other directed back at it.

## To do

- Episodes before 2016 stay rare until older events gain coordinates.
