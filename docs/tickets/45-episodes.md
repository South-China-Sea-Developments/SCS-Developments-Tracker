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

## To do

- The site: the Episodes view on the Events page and an episode's own view (after the design rounds); the
  Episodes tab on the pair pages; the methodology note.
- Episodes before 2016 stay rare until older events gain coordinates.
