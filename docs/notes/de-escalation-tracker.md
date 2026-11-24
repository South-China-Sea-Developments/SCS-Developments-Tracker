# Note: a de-escalation tracker on the same machinery

*Written 2026-10-27 at the maintainer's request, for a possible future project. Nothing here is built; it records the reasoning so it need not be redone.*

## The question

Could this system and methodology study de-escalation instead of (or alongside) escalation, and what would it take to build?

## What carries over unchanged

Everything except the coding scheme and the extraction prompt: the files-are-canonical design (ADR 0004), the harvester and source registry, the relevance filter, the propose/decide review flow (review pull request, review page, Airtable front end), the validator, the site build, the tracker, the scheduled weekly cycle, the release and citation machinery. The new project would start from a copy of this repository (the code is public; the data are Chubb's and stay here) and replace the coding scheme and prompts.

## Where de-escalation already sits in MATS

A MATS move is a step *up* in a claimant's assertiveness on the previous year. Chubb records the mirror image as "cases of diminished assertive actions" (`moves.csv` carries it as `diminished_notes`): a year in which an aspect of earlier assertiveness falls away — a patrol pattern stops, detained crews are released, an annual protest is not repeated. So "a step down" is already a legitimate unit in the framework. Its weakness is that it is de-escalation as *absence*: hard to source and to date, since no document records what did not happen. Usable as a derived, year-level layer; not enough on its own.

## The unit that would be needed

A positive unit: cooperative and conciliatory acts, which MATS deliberately excludes. Hotlines and incident-at-sea arrangements; joint patrols, joint development and fisheries agreements; code-of-conduct milestones; withdrawals of vessels, rigs or survey ships; releases of crews and vessels; statements of restraint; consultation mechanisms and their meetings.

A typology in the spirit of the four MATS types, ordered by weight:

| Type | Content |
|---|---|
| declaratory | statements of restraint, reaffirmations of peaceful settlement, non-escalation pledges |
| institutional | agreements, mechanisms, hotlines, consultation bodies, code-of-conduct steps |
| operational | joint patrols, joint exercises, joint research, coordinated enforcement |
| concessionary | withdrawals, releases, suspensions of activity, dropped claims or protests |

The move logic stays symmetrical: a *cooperative move* is a step up in cooperation on the previous year (qualitative novelty, increased frequency, expanded scope), judged against a baseline of the claimant's cooperative practice.

## Two design rules to settle first

1. **Valence per dyad, not per act.** Many acts cut both ways: a China–Vietnam joint patrol in the Gulf of Tonkin is cooperative within that dyad and can be assertive toward a third party. Code the direction on the dyad, so the same act can be a cooperative move in one dyad and context for an assertive one in another.
2. **The intensification criterion applies.** Routine friendly communiqués are not moves; only a step up in cooperation is. This is what keeps the series from counting every meeting.

## Its own database

A separate database of cooperative moves, with its own schema (the cooperative types; direction coded per dyad), its own baselines and its own site. A net-balance view against assertive moves — cooperative moves above the axis, assertive below — remains the most telling chart, and the new site can draw it by reading this project's published `moves.csv` at a release tag (it is downloadable with checksums and a citation), without either dataset depending on the other.

## Build, as tickets

1. A copy of this repository with the dataset removed; schema and validator for the cooperative types and the dyad-level direction; fixtures.
2. A second extraction prompt (keep two narrow prompts rather than one broad one — the "conservative, literal" instruction works better with a narrow target) and a widened relevance filter (agreement, hotline, joint, release, withdraw, consultation, code of conduct, in the six languages the gazetteer already covers).
3. Baselines of cooperative practice per claimant — the largest human cost, with no MATS to seed it. Event datasets with a cooperation–conflict scale (ICEWS, GDELT's CAMEO codes) can supply *candidates* for a backfill, exactly as the news feeds do now; they do not supply coding.
4. Site: the tracker and Trends pages as they are here, under the new project's own identity; the net-balance chart reading this project's released `moves.csv`.

Each is ticket-sized; the backfill is the long pole.

## Running costs

The same as this tracker's (`docs/handoff.md`): nothing for the site, the data and the review flow; the weekly extraction needs a model or a person to answer the prompt files, interchangeably. A cheap API key is the natural steady-state choice if the cycle should run without anyone's personal account in the loop. Being a personal project, it would use Angelo's own GitHub account and hosting, not the institute's.
