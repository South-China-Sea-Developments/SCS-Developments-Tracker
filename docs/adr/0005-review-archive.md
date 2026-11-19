# 0005. Airtable rows are transient; the record of a review lives in the repository

Date: 2026-11-17. Status: accepted.

## Context

ADR 0004 makes the files canonical and Airtable a front end for the review queue only. The workbench
(tickets 20–21) proved useful enough that every backfill run was mirrored into it, and the base hit the
free plan's cap of 1,000 records per base on 17 Nov 2026 with seven runs (≈440 candidates) still waiting
to be pushed. Reviewing a row does not free its record; only deletion does. The maintainer wants rows
removed or archived once reviewed, without losing anything a coder typed into them (priority, selection,
notes, edits), and without paying for a larger plan.

## Decision

An Airtable row is **transient**: it exists while its candidate awaits a decision and leaves the base when
the decision has been applied to the files. What the coder typed is **archived in the repository** first:
`python -m pipeline.airtable archive --run <run_id> --from export.json` files every exported row of the
run under `harvest/airtable/<run_id>/records.json` (keyed by the code's field names, with the Airtable
record id and the coder's own columns, merged by event id across sittings), writes the decided rows as
the `decisions.json` that `pipeline.queue decide` applies, and lists their Airtable ids in `clear.json`.
The three files are committed on the run's branch and merge with the decisions in the review pull
request; the rows named in `clear.json` are then deleted through the connector, and the run's row in
`Runs` records `archived_on` and a link to the archive folder. Undecided rows stay in the base.

## Alternatives considered

- **A second free base per batch of runs.** Rejected: two workbenches to review in, interfaces and
  automations duplicated, the same cap again a few runs later.
- **Airtable automations to move rows to an archive table or base.** Rejected: there is no delete
  action on the free plan, no scripting action, and an archive table counts against the same cap.
- **A paid plan.** Rejected while the project is unfunded; the files already hold the record.
- **Delete without archiving** (the existing `clear` command). Rejected: the coder's triage columns
  (`note`, `reviewer`, the edits; at the time also `Priority` and `Selected`) would be lost, and the review could not be audited later.

## Consequences

- The base never needs to hold more than the runs under review; the cap stops mattering.
- A review is auditable from the repository alone: the candidate (events.csv), the decision
  (decisions.json, applied in the same pull request), and what the coder saw and typed (records.json).
- `harvest/airtable/` is versioned, unlike `harvest/runs/`; it holds only what the coder produced.
- The Runs table stays as the index of all runs, archived or not (two dozen rows, negligible).
- Pushing a run and archiving it are the two halves of one procedure (`docs/airtable-workbench.md`).
