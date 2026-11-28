# Placing more moves at their reef, shoal, island or field: first proposals (2026-11-28)

Kept from wave 2 by the maintainer. Of the 605 published moves, 343 are not placed at a point: they count
on their sub-regions only. Most name no particular place ("the Spratlys", "Natuna waters", a statement in
a capital), and a point for them would be invented (ticket 34's rule). Some name a place the gazetteer
did not know. This pull request adds five, with their coordinates from the sources below, and places
15 moves that had no point; two moves already placed gain a second point.

**For the maintainer to decide: merge as it is, or say which placements to drop.** Nothing else changes:
the moves' coding and sub-regions are untouched.

## The five places added (`data/reference/gazetteer_extra.csv`)

| Place | Kind | Lat, lon | Source |
|---|---|---|---|
| Natuna Besar (Bunguran) | island | 3.91659, 108.20204 | [Wikipedia](https://en.wikipedia.org/wiki/Natuna_Besar) |
| Bach Long Vi Island | island | 20.13333, 107.72778 | [Wikipedia](https://en.wikipedia.org/wiki/B%E1%BA%A1ch_Long_V%C4%A9_Island) |
| Kasawari gas field (SK316) | field | 4.98030, 112.97870 | [MarineLink](https://ports.marinelink.com/oilrigs/rig/kasawari); GEM gives 4.9817 N |
| Jerun gas field (SK408) | field | 4.61500, 112.09600 | [Global Energy Monitor](https://gem.wiki/Jerun_Gas_Field_(Malaysia)), "exact" |
| East Natuna gas field (Natuna D-Alpha) | field | 4.91490, 109.05100 | [Global Energy Monitor](https://gem.wiki/East_Natuna_Oil_and_Gas_Area_(Indonesia)), "approximate" |

Not added: Hon Ong Island (VN201103; no reliable coordinates found), Capones Island (CN202502 happened
54 nautical miles off it), Con Son Island (VN200904 says "location unknown"), the Tuna block and the
Riau Islands (areas, not points).

## The moves they place

Clear, the act happened at the place:

| Move | Placed at | Why |
|---|---|---|
| ID197402, ID198201 | Natuna Besar | its event's place is "Natuna Island (Natuna Besar)" |
| ID198101 | Natuna Besar | "air base, Natuna Besar" |
| ID201801 | Natuna Besar | the TNI base at Selat Lampa on Natuna Besar |
| ID199401, ID202401 | East Natuna gas field | events at the Natuna D-Alpha field |
| MY202402 | Jerun gas field | first gas at Jerun |
| MY202403 | Kasawari gas field | first gas at Kasawari |
| MY202302, CN202302 | + Kasawari gas field | the Kasawari platform's construction, and the CCG vessel shadowing it (both already placed at Luconia Shoals) |
| VN201002 | Bach Long Vi Island | the president's visit to the island |
| VN202503 | Bach Long Vi Island | the Gulf of Tonkin baseline drawn around it |

Doubtful, the place is a reference point, not where the act happened:

| Move | Placed at | The words |
|---|---|---|
| CN202104 | Natuna Besar | "Tuna block, north of Natuna Besar" |
| ID202101 | Natuna Besar | "about 140 nautical miles north of Natuna Besar" |
| ID199501 | Natuna Besar | "Waters north-east of Natuna Besar" |
| ID199801 | Natuna Besar | "Natuna Sea (Anambas, Natuna Utara, Natuna Besar, Natuna Selatan islands)" |
| VN201601 | Bach Long Vi Island | "southwest of Bach Long Vi Island" |

The matcher places a move at any feature its text names, so "north of X" places it at X. A rule that
skips names after "north of", "off", "km from" and the like would drop these five; it would also move
some existing placements, so it is left for the maintainer to decide (and measured first if he wants it).
