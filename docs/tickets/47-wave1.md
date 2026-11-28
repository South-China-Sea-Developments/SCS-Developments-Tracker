# 47 — Wave 1: new ways to read the moves, on the pages that exist

Proposed on 2026-11-28 (the doc "new tracking views and the next waves"); the maintainer chose views 1, 2,
3, 6 and 7, and asked that they be controls on the existing pages rather than new pages. Each rests only on
fields coded for every move, 1970–2026.

## Built (2026-11-28)

- **Fronts** (view 2): an *Issue* menu on the homepage map (military, administrative, energy, fisheries,
  politics) keeps the map, the counts, the claimant maps and the address (`-i-fis`) to one issue.
- **What moved the score** (view 1): a sub-region's panel compares the five years shown with the five
  before, by claimant and by type, with the change in each; open by default when an arrow shows.
- **How each claimant asserts** (view 3): on Trends, the per-claimant charts switch between type, domain and
  issue, and between per year and each decade's mix (shares on a 0–100 scale; a decade with fewer than 10
  moves is left blank, the rule of Between claimants).
- **How complete the record is** (view 6): a section of the methodology page (`#coverage`, linked from the
  footer): moves by claimant and decade with Chubb's and the project's shares and how many name a feature;
  the languages of the project's sources; events dated and placed by decade.
- **Follow a claimant or a pair** (view 7): `feeds/<claimant>.xml` and `feeds/<a>-<b>.xml`; What's new has
  a button per claimant that narrows the list and points the feed link at that claimant's feed; each pair's
  page has *Follow this pair (feed)*.

## Kept for later

- Placing more moves at their reef or shoal (wave 2): the pipeline proposes a feature for moves whose
  description names one, the maintainer decides; after the ticket 43 audit, so the two do not compete for
  room in the base.
- Not chosen: views 4 (pressure in force) and 5 (firsts). Waves 2 and 3 were set aside by the maintainer, except placing more moves.
