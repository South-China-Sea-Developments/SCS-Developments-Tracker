# SCS Developments Tracker

A continuously updated database of **assertive moves by claimant states in the South China Sea**, built as the successor to Andrew Chubb's *Maritime Assertiveness Time Series* (MATS 1.0, 1970–2015) and its public visualization, the *Maritime Assertiveness Visualization Dashboard* (MAVD, NBR, 2023).

**Status:** project setup. The coding scheme, scope and update pipeline are being decided; see `CONTEXT.md` for the vocabulary and `docs/adr/` for decisions as they are made.

## What is here

| Path | Contents |
|---|---|
| `data/raw/mats-1.02/` | MATS 1.02 as provided by the author (xlsx, plus a verbatim CSV export). 357 cases, 1970–2015. **Never edited.** |
| `data/raw/mavd-arcgis-2023/` | The tables and app configuration behind the public MAVD v1.2 dashboard, pulled from NBR's public ArcGIS services on 2026-10-15. Includes columns absent from the xlsx (`Dates`, `Other_Possible_Cases`, `Cases_of_diminished_assertive_a`). **Never edited.** |
| `data/reference/mavd_subregions.geojson` | The ten MAVD sub-region polygons (WGS84), from the same ArcGIS service. |
| `docs/sources/` | Notes on where each raw input came from and how it was retrieved. |
| `docs/adr/` | Architecture decision records. |
| `CONTEXT.md` | Project glossary. Definitions only. |
| `pipeline/`, `site/`, `tests/` | Reserved for the update pipeline, the public site and their tests. Empty until the spec is agreed. |

## Provenance and citation

The 1970–2015 data are Andrew Chubb's, used with his permission. Any use of this repository's data must cite one or more of:

- Chubb, A. (2022), *Dynamics of Assertiveness in the South China Sea: China, the Philippines, and Vietnam, 1970–2015* (Washington, D.C.: National Bureau of Asian Research). https://www.nbr.org/publication/dynamics-of-assertiveness-in-the-south-china-sea-china-the-philippines-and-vietnam-1970-2015
- Chubb, A. (2021), "PRC Assertiveness in the South China Sea: Measuring Continuity and Change, 1970–2015," *International Security* 45(3): 79–121. https://doi.org/10.1162/isec_a_00400
- Chubb, A. (2022), "Maritime Assertiveness Time Series (MATS 1.0)" dataset, version 1.01, May 18. https://mavd.nbr.org
- Methodology appendix: Chubb, A. (2021), Harvard Dataverse. https://doi.org/10.7910/DVN/3Y7NRU

The MAVD dashboard: https://experience.arcgis.com/experience/679733cea527406bb0aa1b936aa37b90/

## License

Not yet decided (pending agreement with the original author). Until a license file is added, all rights to the data remain with their respective authors.

## Maintainer

Angelo M. (`Angelo-M-SCS`), South-China-Sea-Developments.
