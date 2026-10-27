# Glossary

Definitions only. Terms are added as they are resolved; nothing here is a to-do or an implementation detail. Terms marked *(MATS)* are inherited from Chubb's codebook and keep his meaning.

**Move** *(MATS)* — One case in the dataset: an **intensification of a claimant's assertiveness compared with the previous calendar year**, shown by one of three criteria — qualitative novelty, increased frequency, or expanded geographic scope. A move may be a single action or a closely linked series of actions; an action that merely continues the previous year's behaviour at the same level is not a new move (it is covered by the earlier move's Ongoing-through). The unit of analysis for all MATS variables. Identified by a `CaseID` such as `CN201105` (country code, year, instance number within that year). The source files call this field `AltCaseNo`.

**Event** — A single dated, located, sourced incident (a patrol intercept, a statement, a drilling start). Each event belongs to exactly one move; a move groups one or more events. Dates, coordinates and sources are recorded at event level; MATS variables are not.

**Candidate** — An event proposed by the harvester and not yet decided (`status = candidate`). It has no move and is not counted anywhere.

**Review queue** — The pull request a harvest run opens, holding its candidates, plus the review page generated for it. Merging the pull request is acceptance; nothing enters the dataset otherwise.

**Scheduled run** — The weekly, unattended execution of the harvester on the repository's CI that opens the review queue for its candidates. Its memory between runs (which items each source has already yielded, and a log of each run's cost and yield) is the **harvest state**.

**Decision** — A coder's verdict on a candidate: *merge* it into a move (an existing one, or one formed from another candidate in the same batch), form a *new move* from it (stating the intensification criterion), mark it a *duplicate* of an accepted event (status `merged`, same move), or *reject* it with a note. Applied by `pipeline.queue decide`; the event keeps the machine's suggestions beside the decision.

**Claimant** — A state whose assertive moves are coded. MATS 1.0 covers three: China (`CN`), Vietnam (`VN`), the Philippines (`PH`); this project adds Malaysia (`MY`), Indonesia (`ID`) and Taiwan (`TW`) (decision 03).

**Project coding** — A move or event coded by this project rather than taken from MATS (`coded_by = project`); labelled as such wherever it appears and outside the comparability guarantee.

**Archive (registry)** — A source recorded in the registry as a place to look for 1970–2015 — a chronology, yearbook, government or legal deposit, press archive or scholarly work — with its coverage years and access; never fetched by the harvester.

**Chunk** — One claimant and one decade of the backfill, worked and reviewed as a unit.

**Type** *(MATS)* — The intensity class of a move. Four mutually ordered classes, each a 0/1 flag on the move: **Declarative** (verbal assertions via non-coercive statements, diplomatic protests, legislation); **Demonstrative** (unilateral administration of disputed possessions without confrontation: patrols, surveys, resource development, construction, state-sanctioned tourism or activism, domestic judicial proceedings, cooperative agreements with third parties); **Coercive** (threat or imposition of punishment: verbal, diplomatic, administrative or economic punishment, warning shots, physical interference with foreign activities); **Force** (application of military force, or direct seizure and occupation of a disputed possession).

**Domain** *(MATS)* — The arena a move takes place in. Three, non-exclusive: **Domestic**, **Diplomatic**, **Physical**. Stored as 0/1 flags and as a packed code (`Domains`, e.g. `13` = Domestic + Physical).

**Issue** *(MATS)* — The issue area a move concerns. Five, non-exclusive: **Military**, **Administrative**, **Energy**, **Fisheries**, **Politics**. Stored as 0/1 flags and as a packed code (`Issues`).

**Sub-region** *(MATS)* — One of ten geographic zones of the South China Sea in which a move occurred. Non-exclusive. Numbered 1–10: Tonkin (Gulf of Tonkin), Paracels, Central-West, Central-East, Spratly NW, Spratly NE, Spratly SE, Spratly SW, Nam Con Son, Far South. Polygons in `data/reference/mavd_subregions.geojson`.

**Dyad** *(MATS)* — The pair(s) of states a move is directed between, written actor-first: `CV` = China toward Vietnam, `PC` = Philippines toward China. Codes: R = ROC (Taiwan), C = PRC, P = Philippines, V = Vietnam, M = Malaysia, B = Brunei, I = Indonesia, A = all states in general, U = unclear. A move can have several dyads.

**Ongoing-through** *(MATS)* — The estimated last year in which the behaviour recorded by a move continued. Equals the move's year for one-off events.

**Description** *(MATS)* — The free-text account of a move with its sources cited inline. Called `Case description and sources` in the xlsx and `Intensified_assertive_actions` in the ArcGIS tables.

**Gazetteer** — The project's list of named features of the South China Sea (reefs, shoals, banks, islands) with coordinates, sub-region and names in English, Chinese, Vietnamese, Filipino and Malay. An event whose sources name a feature is placed at it; an event whose sources name only an area is not placed.

**Baseline** *(MATS)* — The known assertive actions of a claimant before 1970, against which its 1970 behaviour is judged for intensification; Chubb published the PRC's list, the project compiles the other five (`data/baselines/`).

**Master timeline** *(MATS)* — Chubb's Stage 1 collection: every plausibly relevant development in the dispute, confirmed or not, from which moves are later refined. In this project the events table plays this role.

**Diminishment** *(MATS)* — A year in which an aspect of a claimant's assertiveness recorded by an earlier move falls away (fewer, or qualitatively less escalatory, actions). Recorded in Chubb's data as "Cases of diminished assertive actions"; absence of evidence of equivalent actions in the following year is normally treated as diminishment.

**Agreement report** — The derived comparison of the machine's suggested coding (Type, Domains, Issues, dyads; the move, where one was proposed) with the coder's final coding, for every accepted event that carried a suggestion, by extractor version and by year, together with what became of every decided suggestion (accepted, duplicate, rejected). Derived from the events and moves, never a file in the dataset.

**Airtable front end** — The optional mirror of a review run's candidates in an Airtable table (`pipeline/airtable.py`), where a coder may decide instead of on the review page; `pull` turns the decisions into the review page's decisions file. Never read when building the dataset or the site (ADR 0004).

**Extraction route** — Who answers the harvester's extraction prompts: the API (`ANTHROPIC_API_KEY`), the Claude Code GitHub Action on the maintainer's subscription (`CLAUDE_CODE_OAUTH_TOKEN`), or a person or assistant in a session. The prompt and the checks are the same on every route; the subscription route is named in the event's `extractor` (`claude-code/<model>`), the API route by the bare model id.

**Prompt files** — A run's extraction prompts written to disk (`harvest/prompts/<run_id>/`: `system.md`, one user prompt per document, `index.json`) and their answers (`harvest/recordings/<run_id>/<key>.json`, the recorded-response format). The contract between the pipeline and whatever answers.

**Relevance filter** — The check that spares the extractor documents naming no South China Sea term or feature (`pipeline/relevance.py`); not a coding judgment. With the per-run cap it bounds what a run costs; documents over the cap are deferred to the next run.

**Token block** — The first block of `web/static/style.css`: the site's faces, colours, kicker style and spacing. Since ticket 17 the colours are the programme banner's (the logo's navy, the sea's teals) and the manner is CFR's Global Conflict Tracker; one colour scheme, no dark mode.

**The banner** — The "South China Sea Research Initiative" image the maintainer supplied (`web/static/img/banner.jpg`, logo and title as sent, served as a 2× upscale until the institute's original replaces it at the same path), the header of every page. The site presents itself as the institute's at the maintainer's request (decision 06, amended 2026-10-27).

**The tracker** — The home page (`index.html`, also served as `map.html`): a dark sidebar — title, the count of events in view, search, filters with the claimant dots as legend, time controls, the events in view newest first — beside the event map, filling the viewport under the navigation band; white like the rest of the site since ticket 18. The charts live on the Trends page.

**Kicker** — The small bold letter-spaced capitals over a page title, on the navigation, the sidebar's group labels, the brand name and the footer headings; the site's one all-caps style.

**Published move** — An accepted move. The site publishes accepted moves only: a pending move has no page, no row and no count anywhere on the site until it is accepted (ticket 17); the files and `aggregates.json` keep it as data.

**Dataset version** — The number this project gives the dataset (`DATASET_VERSION`, `MAJOR.MINOR.PATCH`, a `-dev` suffix while it is being built), written on every project-coded move as `data_version`. Versions 1.x are Chubb's MATS; this project's are 2.x.

**Release** — A dataset version fixed as a git tag `vX.Y.Z[-suffix]` on `main`; what the Downloads page and the GitHub Release serve, with checksums and a citation.

**MATS** — Maritime Assertiveness Time Series, Chubb's dataset. Version 1.02 is the raw input to this project.

**MAVD** — Maritime Assertiveness Visualization Dashboard, NBR's public ArcGIS front end for MATS (v1.2, February 2023).
