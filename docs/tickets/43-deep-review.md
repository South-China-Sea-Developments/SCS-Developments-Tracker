# 43 — Deep review of every record the maintainer decided, and the re-review loop

Asked by the maintainer on 2026-11-25: once he has decided the 700-odd candidates still in Airtable, Fable
is to go through every record he added and checked, and test every metric: the location, the reason he
accepted or rejected it, whether similar moves coded by Chubb were coded differently, whether each is
really coercive or declarative (or something else), and so on. Where the audit disagrees, the record goes
to a "to be re-reviewed" step in Airtable carrying the audit's alternative coding and its reasoning; his
answers go back to the data on GitHub and so to the website. **Not to be run until he says so.**

## Scope

- The project's own records: the moves coded by the project (`coded_by = project`, 128 on 2026-11-25)
  and the harvested events he decided (accepted, rejected or merged: 630 on 2026-11-25, more as the
  remaining candidates are decided).
- Chubb's moves (MATS 1.02) are the benchmark the audit compares against. They are never re-coded here
  (ADR 0001).

## What the audit tests, record by record

1. **Place**: the feature, coordinates, precision and sub-region against the sources and the gazetteer;
   the move's sub-region flags against its events.
2. **The decision**: whether the accept or reject, and the note behind it, holds against the sources and
   the coding guide, and whether it is consistent with how the maintainer decided like cases elsewhere.
3. **Chubb's practice**: the comparable MATS cases (same claimant or a rival, the same kind of act, nearby
   years) and how Chubb coded them; a difference is a finding.
4. **Type**: declarative, demonstrative, coercive or use of force, by the coding guide's boundaries and
   the maintainer's binding rulings (below); then the domains, issues and dyads.
5. **The move**: whether a new move really is a year-on-year intensification (novelty, frequency or
   scope) and its criterion; whether an event belongs to the move it is in; ongoing-through years.
6. **Dates and text**: the date and its precision; the summary and the move description against the sources.

## The loop

1. **Audit** (unattended, long; `docs/audit-prompt.md`): writes findings only where it disagrees, one per
   record and field, each with the current value, the proposed value, the reasoning, the source passages,
   the comparable Chubb cases, and a confidence.
2. **Rows**: `python -m pipeline.rereview rows` checks every finding against the data (the record exists
   and is the project's, the field is one a finding may address, the current value is what the data
   holds, the proposal parses and differs) and writes the rows for the base's **Re-review** table.
   The rows go in as room allows under the free plan's 1,000-record cap.
3. **Re-review** (the maintainer, in Airtable): each row is answered **keep** (the current coding stands),
   **take** (the proposal) or **edit** (his own value in *Your value*), with an optional note.
4. **Apply**: `python -m pipeline.rereview apply` writes the answers into `data/`, appends a
   `[re-review DATE: field old -> new; note]` mark to each changed event's review note, archives the
   sitting under `harvest/airtable/rereview/` (records, the applied report, the rows to clear), and names
   the rows to clear. A row whose record changed since the finding was made is skipped and stays in the
   base. Rejecting the last event of a move is refused: the move's *withdraw* finding decides that (it
   removes the move and rejects its events). The change goes through a pull request, merged once the
   validator and CI accept it (decision 07: his answers are his review), and the site rebuilds.

The fields a finding may address, and how values are written, are listed in `pipeline/rereview.py`.

## Reference texts

The audit reasons from Chubb's own words: the methodological appendix (`docs/codebook/`), the MATS 1.02
narratives (`data/raw/mats-1.02/`), and the full texts of the *International Security* article (2021) and
NBR Special Report 99 (2022). Those two are copyrighted and this repository is public, so they live in a
private companion repository, `South-China-Sea-Developments/scs-tracker-references`, which the audit clones.

## Binding rulings from the maintainer

The maintainer found that Opus misread some boundaries, in particular coercive vs use of force and
coercive vs declarative, and that the right lines are Chubb's own (2026-11-25): use of force is the taking
of a feature, and violence against people or vessels is coercive however severe (the example: CCG
personnel beating fishermen, `CN202406`, coded force by mistake); a claim without a threat of punishment is
declarative however strong its words. Written into `docs/coding-guide.md` §II.G as *The maintainer's binding
rulings*, and into the extraction prompt and the research brief so new suggestions follow them. The audit
treats them as binding.

## Status

- Built 2026-11-25: `pipeline/rereview.py` (rows, apply, archive) with tests; the Re-review table in the
  base (`tblR8Lb34BDuu6KjF`); `docs/audit-prompt.md`; the weekly task applies decided Re-review rows.
- Waiting: the references repository (to be created by the maintainer) and his go-ahead once the
  candidates are decided.
