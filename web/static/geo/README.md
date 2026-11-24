# Reference lines for the home map (ticket 27)

Optional layers on the assertiveness map, off by default, clipped to 95–130° E, 5° S–30° N.

| File | Source | What it is |
|---|---|---|
| `eez.geojson` | Flanders Marine Institute (2023), Maritime Boundaries Geodatabase v12, layer `eez_boundaries` (WFS `geo.vliz.be/geoserver/MarineRegions`), retrieved 2026-11-23; **CC BY 4.0**, https://doi.org/10.14284/632 | EEZ boundary lines between and around the claimants (treaty, median, unsettled and 200-nm lines), clipped to 103.5–122.5° E, 0.5–23.5° N and simplified (0.01°). Baselines and connection lines are left out. In the Spratlys and Paracels Marine Regions draws overlapping claims as areas, not lines, so few lines cross the middle of the sea. |
| `reefs.geojson` | Natural Earth 1:10m `reefs` | Reef outlines (lines), drawn faintly from zoom 5.5 to make the features precise without changing the far view. |
| `islands.geojson` | Natural Earth 1:10m `minor_islands`, those wholly inside 104–121.5° E, 2–23° N | Small islands the basemap omits at low zoom, drawn faintly from zoom 5.5. |
| `dashline.geojson` | Natural Earth 1:10m `admin_0_boundary_lines_maritime_indicator_chn` (features with the comment "Chinese 9 dash line") | The dashed line China (and Taiwan) draw, shown as a claim, not a boundary. |

Natural Earth is in the public domain; Marine Regions asks for attribution (CC BY 4.0), given on the map. Retrieved 2026-11-22 from `github.com/nvkelso/natural-earth-vector` (`geojson/`).
