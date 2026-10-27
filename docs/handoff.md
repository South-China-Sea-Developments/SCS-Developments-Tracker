# Handoff: resuming this project from any account, or none

*Written 2026-10-27. For the maintainer, or anyone he hands the project to, picking it up later in a new session, on another Claude account, or without one.*

## What the project is, in one paragraph

A continuously updated database of assertive moves by claimant states in the South China Sea, continuing Andrew Chubb's MATS 1.02 past 2015 and to six claimants with the same coding rules, with a public static site. Machines propose candidate events from registered sources; a person decides every one. The files in `data/` are the dataset; everything else is derived from them.

## Everything lives in the repository

`https://github.com/South-China-Sea-Developments/SCS-Developments-Tracker` holds the code, the data, the site templates and all of the project's memory: `CONTEXT.md` (glossary), `docs/spec.md` (the spec and its amendments), `docs/decisions/` and `docs/adr/` (the decisions and their reasons), `docs/tickets/` (what was built, how, and what is left), `docs/notes/` (ideas recorded for later). Nothing about the project is stored only in a chat, a session or an account. To resume anywhere: clone the repository and read, in order, `README.md`, `CONTEXT.md`, `docs/spec.md`, `docs/decisions/README.md`, `docs/tickets/README.md`.

To resume with Claude on another account: open a session with repository access (the Claude app or Claude Code), point it at the repository, and ask it to read those files and `docs/handoff.md`. The working method (`project-conduct`: align, spec, tickets, build in verified steps, review on two axes, hand off cleanly) is an Anthropic-provided skill available to any account; the project's own skill, `.claude/skills/harvest-extract/SKILL.md`, is in the repository.

## What is bound to an account, and how to recreate it

Only three things are outside the repository:

1. **The weekly scheduled task** (Claude app, "SCS Tracker weekly harvest", Mondays 02:17 New York time, automatic approval, push notifications). It runs the "session route" of ticket 14: fetch, write prompts, answer them with the session's own model, extract, open the review pull request, push the state. It is bound to the account that created it; on a new account, create a scheduled task with the prompt in `docs/scheduled-task-prompt.md` (verbatim), the same schedule, and the GitHub connection for the maintainer's account. Without any scheduled task, the GitHub Actions workflow (`.github/workflows/harvest.yml`, dispatch only) still fetches and writes prompts and opens a "harvest waiting" issue; see "Extraction without an API key" in `README.md`.
2. **The Airtable review base** (`pipeline/airtable.json`: base, table and interface ids). It lives in the maintainer's Airtable workspace, not in any Claude account, so it survives an account change; a new session needs the Airtable connector to load records through the app, or an `AIRTABLE_TOKEN` secret for the REST route (never created so far, by decision).
3. **GitHub access**: pushes and pull requests go through the maintainer's GitHub account (`Angelo-M-SCS`), whichever tool makes them.

## The weekly cycle, and what it costs

| Step | Who or what | Cost |
|---|---|---|
| Fetch the registered sources, filter for relevance, write prompt files | GitHub Actions or the scheduled session | none (public repository) |
| Answer the prompts (turn documents into candidate events) | a Claude subscription (the scheduled task), **or** an API key as a repository secret (`ANTHROPIC_API_KEY`; pay per use, on the order of a dollar or two a week at the 80-document cap), **or** a person answering the prompt files | the only step that needs a model |
| Review the candidates (review page or Airtable) | a person, always | minutes a week |
| Build and publish the site | GitHub Actions on merge to `main` | none |

Hosting: GitHub Pages now, the institute's site later (the bundle is portable, relative paths only). Map tiles: OpenFreeMap, free, no key. If the subscription lapses, the scheduled task stops and nothing else breaks; candidates stop arriving until someone answers the prompts or a key is added.

## Open items at the time of writing

- Review pull requests #17 (24 candidates, ticket 11's baselines) and #24 (3 candidates, the first live harvest).
- Questions for Andrew Chubb: licence, credit line, the xlsx/online discrepancies, `VN197304`, citation version.
- Branch protection on `main`; the institute's hosting; aggregator feeds that yield headline-only captures (the fetcher should resolve article links).
- `docs/notes/de-escalation-tracker.md`: a possible second coding scheme on the same machinery.
