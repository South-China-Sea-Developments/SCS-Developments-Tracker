# 33 — Sub-regions suggested at harvest time

Improvement 1 of the eight agreed on 2026-11-23. Many candidates name no reef ("off Sabah and Sarawak",
"Block SC 75, west of Palawan", "the Bruneian EEZ") and reached the coder with the sub-region blank.

- `data/reference/areas.csv` (52 areas, made by `pipeline.areas_build` by hand): the sea within about
  150 km of each coastal province (Natural Earth admin-1, public domain; widened to 220 or 300 km where
  the sub-region polygons stop short of the coast, as off southern Vietnam), the six claimants' EEZs
  (Marine Regions v12, CC BY 4.0), three named seas, and oil blocks from sourced points
  (`area_points.csv`: Block K). Each holds only its share of each sub-region, no geometry.
- `pipeline.places.suggest_subregions(event)`: the event's coordinates; else the features and areas its
  place names; else those its summary names. An area counts the sub-regions holding at least 15% of it;
  an EEZ counts only when nothing narrower is named.
- In Airtable, a candidate without a sub-region now arrives with "New move: sub-regions" prefilled from
  the suggestion, the single "Sub-region" only when there is one, and the reason in the machine note,
  e.g. "Sub-regions suggested: 10 Far South (Sabah coast 15%; Sarawak coast 99%); 7 Spratly SE (Sabah
  coast 85%)." The event row is not changed; the coder decides.
- Checked against the 69 events whose sub-region is coded: right sub-region first for 60, listed for 3,
  none suggested for 6, never wrong (a test holds it at 85% first and none wrong).
- Records already in Airtable are not touched; new pushes carry the suggestion.
