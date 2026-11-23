# Reference lines for the home map (ticket 27)

Optional layers on the assertiveness map, off by default, clipped to 95–130° E, 5° S–30° N.

| File | Source | What it is |
|---|---|---|
| `maritime.geojson` | Natural Earth 1:10m `admin_0_boundary_lines_maritime_indicator` | Indicative maritime boundaries between neighbours (median lines, treaty lines, disputed lines). Not the legal limits of any zone. |
| `reefs.geojson` | Natural Earth 1:10m `reefs` | Reef outlines (lines), drawn faintly from zoom 5.5 to make the features precise without changing the far view. |
| `islands.geojson` | Natural Earth 1:10m `minor_islands`, those wholly inside 104–121.5° E, 2–23° N | Small islands the basemap omits at low zoom, drawn faintly from zoom 5.5. |
| `dashline.geojson` | Natural Earth 1:10m `admin_0_boundary_lines_maritime_indicator_chn` (features with the comment "Chinese 9 dash line") | The dashed line China (and Taiwan) draw, shown as a claim, not a boundary. |

Natural Earth is in the public domain. Retrieved 2026-11-22 from `github.com/nvkelso/natural-earth-vector` (`geojson/`).
