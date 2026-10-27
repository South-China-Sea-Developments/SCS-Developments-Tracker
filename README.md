# SCS Developments Tracker

A continuously updated database of **assertive moves by claimant states in the South China Sea**, built as the successor to Andrew Chubb's *Maritime Assertiveness Time Series* (MATS 1.0, 1970–2015) and its public visualization, the *Maritime Assertiveness Visualization Dashboard* (MAVD, NBR, 2023).

**Status:** building. Decisions are settled (`docs/adr/`, `docs/decisions/`), the spec is confirmed (`docs/spec.md`) and work proceeds by ticket (`docs/tickets/`). Done so far: the canonical files hold MATS 1.02 and pass the validator in CI (01); the public site has the overview, issues/domains, sub-regions, case browser and methodology pages (02–04); the harvester fetches the registered sources and proposes candidate events (05); a run becomes a review pull request with a review page, and decisions are applied with one command (06); the run is scheduled weekly, with failure issues and review reminders (07); the site has an event map with a time slider and filters, and a gazetteer places events at named features (08); releases are tags, with a Downloads page, checksums and a citation (09); the methodology page reports machine–coder agreement (10); baselines for all six claimants and hand-compiled candidate sets enter the same queue (11); the archival source lists and routine for the 1970–2015 backfill are in place, coding not started (12); candidates can be reviewed in Airtable with the decisions landing in the pull request unchanged (13); the weekly extraction can run on the maintainer's Claude subscription instead of an API key (14); the site has one coherent visual system with a home page that leads with the map and the latest developments (15); its type, hero and map panel follow the three references the maintainer supplied (16); the home page is a tracker in the manner of CFR's under the institute's banner, with the charts on a Trends page and nothing about the project's own progress on show (17); the tracker is white like the rest of the site and the banner sharper (18).

**Site:** https://south-china-sea-developments.github.io/SCS-Developments-Tracker/ (rebuilt on every merge to `main` and on every release tag). **Harvest:** every Monday on GitHub Actions; review pull requests are the queue.

## Quick start

```
pip install -e ".[dev]"
python -m pytest                   # tests at the canonical-file seam
python -m pipeline.validate        # checks data/*.csv against the schema and MATS 1.02
python -m pipeline.load_mats       # regenerates data/*.csv from data/raw/
python -m web.build                # builds the site into web/dist/ (open web/dist/index.html)
python -m pipeline.harvest probe   # checks the registered sources are reachable
python -m pipeline.harvest run     # fetches new items and extracts candidate events (needs ANTHROPIC_API_KEY)
python -m pipeline.harvest prompts --captures harvest/captures/<id> --out harvest/prompts/<id> --max-documents 80   # the prompts as files, for the subscription or session route
python -m pipeline.harvest extract --captures harvest/captures/<id> --out harvest/runs/<id> --prompts harvest/prompts/<id> --recordings harvest/recordings/<id>   # candidates from the answers
python -m pipeline.harvest import events.json --run-id <id> --extractor "who"   # hand-compiled candidates into the same queue
python -m pipeline.queue open --run harvest/runs/<run_id>   # branch + review page + pull request
python -m pipeline.queue decide decisions.json --reviewer "Name"   # apply the coder's decisions, commit
python -m pipeline.airtable push --run <run_id> --pr N   # mirror a run's candidates into the Airtable review table (needs AIRTABLE_TOKEN)
python -m pipeline.airtable pull --run <run_id> --out decisions.json   # the decisions made there, as the file `queue decide` reads
python -m pipeline.ops --help      # what the scheduled run does around a harvest: state branch, failure issue, reminders
python -m pipeline.agreement       # machine suggestions vs the coder's final coding, as a Markdown table
python -m pipeline.release latest  # the newest release tag; `assets --out DIR` writes the downloadable files for it (docs/releases.md)
```

## What is here

| Path | Contents |
|---|---|
| `data/*.csv` | **The canonical dataset**: claimants, moves, events, sources, corrections. See `data/README.md`. |
| `data/baselines/` | Each claimant's pre-1970 baseline list (Chubb's for the PRC; the project's, sourced, for the other five; provenance in `docs/sources/`). |
| `harvest/manual/` | Hand-compiled candidate sets kept on record before they enter the review queue. |
| `pipeline/` | Loader, validator, harvester (source registry, fetcher, extractor and its prompt), review queue, Airtable front end (`airtable.py`, `airtable.json`), scheduled-run operations, releases, agreement report. |
| `harvest/` | Working folder for harvest runs (not committed; the state between runs lives on the `harvest-state` branch). |
| `docs/review/` | Review pages, one per harvest run. |
| `tests/` | Tests at the agreed seams. |
| `docs/spec.md`, `docs/tickets/` | What is being built and in which slices. |
| `docs/backfill.md` | How a 1970–2015 chunk for Malaysia, Indonesia or Taiwan is coded and reviewed. |
| `docs/handoff.md`, `docs/scheduled-task-prompt.md` | How to resume the project from any account or none; the weekly task's prompt, verbatim. |
| `docs/notes/` | Ideas recorded for later (a de-escalation tracker on the same machinery). |
| `CHANGELOG.md`, `CITATION.cff`, `docs/releases.md` | What each tagged version holds, how to cite it, how a release is made. |
| `docs/decisions/`, `docs/adr/` | Why. |
| `docs/codebook/` | Chubb's methodology appendix (CC0), the coding rules. |
| `docs/reports/` | Generated reports, e.g. xlsx-vs-MAVD differences for the author. |
| `data/raw/mats-1.02/` | MATS 1.02 as provided by the author (xlsx, plus a verbatim CSV export). 357 cases, 1970–2015. **Never edited.** |
| `data/raw/mavd-arcgis-2023/` | The tables and app configuration behind the public MAVD v1.2 dashboard, pulled from NBR's public ArcGIS services on 2026-10-15. Includes columns absent from the xlsx (`Dates`, `Other_Possible_Cases`, `Cases_of_diminished_assertive_a`). **Never edited.** |
| `data/reference/mavd_subregions.geojson` | The ten MAVD sub-region polygons (WGS84), from the same ArcGIS service. |
| `data/reference/gazetteer.csv`, `gazetteer_extra.csv` | Named features of the sea (reefs, shoals, banks, islands) with coordinates, sub-region and names in five languages: generated from Wikidata (`pipeline.gazetteer_wikidata`) plus hand corrections. Places harvested events. |
| `docs/sources/` | Notes on where each raw input came from and how it was retrieved. |
| `CONTEXT.md` | Project glossary. Definitions only. |
| `.claude/skills/harvest-extract/` | The skill that answers a run's extraction prompts (used by the weekly run on the subscription route and in sessions). |
| `web/` | The public site: build script, templates, stylesheet, chart and map scripts, vendored font, MapLibre and basemap style. Output in `web/dist/` (not committed). |

## Extraction without an API key

The weekly run needs a language model only for one step, turning fetched documents into candidate events. Since 2026-10-26 it is a scheduled task on the maintainer's Claude subscription that performs the session route below every Monday (decision 08); no key or token is stored anywhere. The GitHub Actions workflow (`.github/workflows/harvest.yml`) is run on demand, and which credential exists decides its route:

- `ANTHROPIC_API_KEY` (API billing): the pipeline calls the API itself.
- `CLAUDE_CODE_OAUTH_TOKEN` (a Claude subscription; from `claude setup-token`): the pipeline writes the prompts as files, the Claude Code GitHub Action answers them with the `/harvest-extract` skill on the maintainer's subscription, and the pipeline reads the answers. A relevance filter (`pipeline/relevance.py`) drops documents that name no South China Sea term or feature, and `max_documents` (default 80 a run, shared round-robin across sources so the agency listings are never crowded out by news feeds) defers the rest to the next run, so a week costs the subscription as little as possible. A deferred document comes back only while its source still lists it, so if the run summary shows deferrals two weeks running, raise `max_documents`. Adding the secret starts a review pull request every Monday; removing it (or disabling the workflow under Actions) pauses that. The answers are named `claude-code/<model>` in the `extractor` field, so the agreement report keeps this route apart from the API's.
- Neither: the run fetches, opens one "waiting for extraction" issue and leaves the state untouched; nothing is lost (the fetched captures are kept 90 days as the run's artifact, and a document still listed by its source is fetched again). The same prompts can then be answered in a session, when the maintainer asks for it (decision 07): `python -m pipeline.ops state pull`; `python -m pipeline.harvest fetch --out harvest/captures/<id> --state harvest/state.json`; `python -m pipeline.harvest prompts --captures harvest/captures/<id> --out harvest/prompts/<id> --max-documents 80 --answered-by claude-code/<model>`; the `/harvest-extract` skill; `python -m pipeline.harvest extract --captures harvest/captures/<id> --out harvest/runs/<id> --prompts harvest/prompts/<id> --recordings harvest/recordings/<id>`; `python -m pipeline.queue open --run harvest/runs/<id>`; and `python -m pipeline.ops state push --run-id <id> --report harvest/runs/<id>/run.json --captures harvest/captures/<id>`, without which the next scheduled run proposes the same documents again.

Whichever route answers, the prompt, the parsing and every check are the pipeline's, and every candidate still goes to a human coder (ADR 0003).

## Provenance and citation

The 1970–2015 data are Andrew Chubb's, used with his permission. Any use of this repository's data must cite one or more of:

- Chubb, A. (2022), *Dynamics of Assertiveness in the South China Sea: China, the Philippines, and Vietnam, 1970–2015* (Washington, D.C.: National Bureau of Asian Research). https://www.nbr.org/publication/dynamics-of-assertiveness-in-the-south-china-sea-china-the-philippines-and-vietnam-1970-2015
- Chubb, A. (2021), "PRC Assertiveness in the South China Sea: Measuring Continuity and Change, 1970–2015," *International Security* 45(3): 79–121. https://doi.org/10.1162/isec_a_00400
- Chubb, A. (2022), "Maritime Assertiveness Time Series (MATS 1.0)" dataset, version 1.01, May 18. https://mavd.nbr.org (the author's suggested citation as given in the xlsx; the file supplied to this project is version 1.02)
- Methodology appendix: Chubb, A. (2021), Harvard Dataverse. https://doi.org/10.7910/DVN/3Y7NRU

The MAVD dashboard: https://experience.arcgis.com/experience/679733cea527406bb0aa1b936aa37b90/

To cite this continuation: see `CITATION.cff` or the site's Downloads page (version and date from the release tag).

## License

Not yet decided (pending agreement with the original author). Until a license file is added, all rights to the data remain with their respective authors.

## Maintainer

Angelo M. (`Angelo-M-SCS`), South-China-Sea-Developments.
