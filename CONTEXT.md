# Glossary

Definitions only. Terms are added as they are resolved; nothing here is a to-do or an implementation detail. Terms marked *(MATS)* are inherited from Chubb's codebook and keep his meaning.

**Move** *(MATS)* — One case in the dataset: an **intensification of a claimant's assertiveness compared with the previous calendar year**, shown by one of three criteria — qualitative novelty, increased frequency, or expanded geographic scope. A move may be a single action or a closely linked series of actions; an action that merely continues the previous year's behaviour at the same level is not a new move (it is covered by the earlier move's Ongoing-through). The unit of analysis for all MATS variables. Identified by a `CaseID` such as `CN201105` (country code, year, instance number within that year). The source files call this field `AltCaseNo`.

**Event** — A single dated, located, sourced incident (a patrol intercept, a statement, a drilling start). Each event belongs to exactly one move; a move groups one or more events. Dates, coordinates and sources are recorded at event level; MATS variables are not.

**Candidate** — An event proposed by the harvester and not yet decided (`status = candidate`). It has no move and is not counted anywhere.

**Review queue** — The pull request a harvest run opens, holding its candidates, plus the review page generated for it. Merging the pull request is acceptance; nothing enters the dataset otherwise.

**Scheduled run** — The weekly, unattended execution of the harvester on the repository's CI that opens the review queue for its candidates. Its memory between runs (which items each source has already yielded, and a log of each run's cost and yield) is the **harvest state**, kept on a branch of its own that is never merged.

**Decision** — A coder's verdict on a candidate: *merge* it into a move (an existing one, or one formed from another candidate in the same batch), form a *new move* from it (stating the intensification criterion), mark it a *duplicate* of an accepted event (status `merged`, same move), or *reject* it with a note. Applied by `pipeline.queue decide`; the event keeps the machine's suggestions beside the decision.

**Claimant** — A state whose assertive moves are coded. MATS 1.0 covers three: China (`CN`), Vietnam (`VN`), the Philippines (`PH`).

**Type** *(MATS)* — The intensity class of a move. Four mutually ordered classes, each a 0/1 flag on the move: **Declarative** (verbal assertions via non-coercive statements, diplomatic protests, legislation); **Demonstrative** (unilateral administration of disputed possessions without confrontation: patrols, surveys, resource development, construction, state-sanctioned tourism or activism, domestic judicial proceedings, cooperative agreements with third parties); **Coercive** (threat or imposition of punishment: verbal, diplomatic, administrative or economic punishment, warning shots, physical interference with foreign activities); **Force** (application of military force, or direct seizure and occupation of a disputed possession).

**Domain** *(MATS)* — The arena a move takes place in. Three, non-exclusive: **Domestic**, **Diplomatic**, **Physical**. Stored as 0/1 flags and as a packed code (`Domains`, e.g. `13` = Domestic + Physical).

**Issue** *(MATS)* — The issue area a move concerns. Five, non-exclusive: **Military**, **Administrative**, **Energy**, **Fisheries**, **Politics**. Stored as 0/1 flags and as a packed code (`Issues`).

**Sub-region** *(MATS)* — One of ten geographic zones of the South China Sea in which a move occurred. Non-exclusive. Numbered 1–10: Tonkin (Gulf of Tonkin), Paracels, Central-West, Central-East, Spratly NW, Spratly NE, Spratly SE, Spratly SW, Nam Con Son, Far South. Polygons in `data/reference/mavd_subregions.geojson`.

**Dyad** *(MATS)* — The pair(s) of states a move is directed between, written actor-first: `CV` = China toward Vietnam, `PC` = Philippines toward China. Codes: R = ROC (Taiwan), C = PRC, P = Philippines, V = Vietnam, M = Malaysia, B = Brunei, I = Indonesia, A = all states in general, U = unclear. A move can have several dyads.

**Ongoing-through** *(MATS)* — The estimated last year in which the behaviour recorded by a move continued. Equals the move's year for one-off events.

**Description** *(MATS)* — The free-text account of a move with its sources cited inline. Called `Case description and sources` in the xlsx and `Intensified_assertive_actions` in the ArcGIS tables.

**Master timeline** *(MATS)* — Chubb's Stage 1 collection: every plausibly relevant development in the dispute, confirmed or not, from which moves are later refined. In this project the events table plays this role.

**Diminishment** *(MATS)* — A year in which an aspect of a claimant's assertiveness recorded by an earlier move falls away (fewer, or qualitatively less escalatory, actions). Recorded in Chubb's data as "Cases of diminished assertive actions"; absence of evidence of equivalent actions in the following year is normally treated as diminishment.

**MATS** — Maritime Assertiveness Time Series, Chubb's dataset. Version 1.02 is the raw input to this project.

**MAVD** — Maritime Assertiveness Visualization Dashboard, NBR's public ArcGIS front end for MATS (v1.2, February 2023).
