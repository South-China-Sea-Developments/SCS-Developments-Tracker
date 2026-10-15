# Raw inputs: provenance

## MATS 1.02 (`data/raw/mats-1.02/`)

- `MATS_1-02_all_cases.xlsx`: supplied by the author (Andrew Chubb) to the maintainer, 2026-10. Two sheets: `MATS 1.02 cases` (357 rows × 33 columns) and `Information` (citation and column notes).
- `MATS_1-02_all_cases.csv`: verbatim export of the cases sheet, UTF-8, no transformation.

Profile (2026-10-15): years 1970–2015; CN 144, VN 111, PH 102 moves. `OrgCaseNo` is empty for 16 moves. No dates finer than year, no coordinates, no structured source fields.

## MAVD v1.2 ArcGIS services (`data/raw/mavd-arcgis-2023/`)

Retrieved 2026-10-15 from NBR's public ArcGIS Online organisation (`nbr-org.maps.arcgis.com`, services host `services5.arcgis.com/y4SJJ5lIYCbQmakL`). All items are publicly readable; nothing was authenticated.

| File | Source | Notes |
|---|---|---|
| `experience_builder_config.json` | Item `679733cea527406bb0aa1b936aa37b90` (Web Experience "Maritime Assertiveness Visualization Dashboard (MAVD) v1.2", owner `kkarnikis`, modified 2023-02-10) | Page layout, widgets, chart definitions and explanatory text of the dashboard. |
| `webmap_MAVD12.json` | Web map item `9f95041a7a5549fb863292d4de34b5ed` ("MAVD12") | Layer list: sub-regions, estimated maximum EEZ claims (tile layers, one per claimant), claim lines, and the statistics tables. |
| `webmap_MAVD_JAN_2023.json` | Web map item `7824a96f32fb4db4adf52d6991538612` ("MAVD_JAN_2023") | Per-sub-region, per-country point layers used for the map "spiral" display. |
| `All_Actions7.csv` | `MAVD0514227/FeatureServer/2` (table `All_Actions7`) | 372 rows: 358 moves plus 14 placeholder rows for country-years with no move (`AltCaseNo` empty). Compared with the xlsx: one extra move (`VN197304`); 75 descriptions differ in wording; three columns absent from the xlsx: `Dates` (103 filled), `Other_Possible_Cases` (77), `Cases_of_diminished_assertive_a` (57). |

Other services of interest (not downloaded; queryable):

- `MAVD0514227/FeatureServer/0` `All_Actions_Subregion7XY` (930 rows): one point per move × sub-region. **Coordinates are synthetic** (spread inside the sub-region polygon for display), not event locations.
- `Physical_Domain_{CN,VN,PH}_01302023/FeatureServer/0`: physical-domain moves as points; same synthetic coordinates.
- `MAVD0514227/FeatureServer/3`–`8`: pre-aggregated statistics (country × year × type; dyads).
- `VNPHCNMAVDCLAIMS/FeatureServer/0`: six claim polylines (China, Philippines, Vietnam).
- EEZ tile layers `EE2MASASDAFDIOAP4ZTST{BR2,CH7,IN2,MA2,PH2,TA3,VI5}/MapServer`: estimated maximum EEZ claims per claimant (raster tiles only).

## Sub-region polygons (`data/reference/mavd_subregions.geojson`)

`MAVD0514227/FeatureServer/1` (`MAVD_ALL_Detail_Lat_Lon_TS7b`), exported as GeoJSON in WGS84. Ten polygons; `LocationNo` 1–10 matches the MATS sub-region numbering. Attribute columns `XX_1971_75` etc. are MAVD's five-year counts and can be regenerated from the moves.
