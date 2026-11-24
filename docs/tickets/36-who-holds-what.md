# 36 — Who holds what

Improvement 6 of the eight agreed on 2026-11-23.

- `data/reference/occupation.csv` (58 features), made by `pipeline.occupation_build` from the occupation
  table of English Wikipedia's "List of maritime features in the Spratly Islands" (retrieved 2026-11-23),
  matched to the gazetteer by name, then position; plus the Paracel Islands (all held by China since
  January 1974) and Scarborough Shoal (controlled by China since 2012, no structure). Vietnam 28,
  Philippines 11, China 9 (with the Paracels and Scarborough), Malaysia 7, Taiwan 2.
- Left out: Louisa Reef, which the same article gives to Brunei while saying Malaysia keeps a
  lighthouse there.
- Gazetteer fixes found on the way: Ladd Reef's position (Wikidata had it about 95 km off; now
  8°39′57″N 111°40′36″E), Bombay Castle added (Vietnam's platform on Rifleman Bank), Ban Than Reef
  renamed from its Filipino name, Collins Reef capitalised.
- On the home map, "Who holds each feature" under "On the map" (off by default, in the link as `-l-h`):
  a ring in the holder's colour at each held feature, and a label at the Paracels. Feature pages and
  the map's feature panel say who holds it; features in the Paracels sub-region take the group's holder.
