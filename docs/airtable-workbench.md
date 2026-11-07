# The Airtable workbench

How the review base is organised and how a run is pushed into it (ticket 20). The base is a
front end only: the files in the repository stay canonical (ADR 0004) and nothing that builds
the dataset or the site reads Airtable. The layout follows the maintainer's working sheet for
the Taiwan Policy Database ("TPD Updates"), tab for tab.

Base `appK9OckCTV15vQwx`, interface "Review queue" `pbdWq70PPQffUrIye`
(https://airtable.com/appK9OckCTV15vQwx/pbdWq70PPQffUrIye).

## Tables

| Table | id | TPD Updates equivalent | What it holds |
|---|---|---|---|
| `Candidates` | `tbl1jZACWLq6FXPOq` | Timeline / Working | One record per candidate event of a review pull request: the review page's context, the coder's decision columns, and (ticket 20) `flags`, `dataset_status`, `run`, `added_on`, `decided_on`. `pipeline/airtable.py` owns its schema. |
| `Runs` | `tblLK3YqY7mDL2QqW` | Run Log | One row per harvest or backfill run: date, type (Weekly harvest / Backfill / Manual / Catch-up), scope, verdict, documents, candidates, possible duplicates, failures, excerpts verified / unchecked / not found, review PR, extractor, unreachable sources, what to look at. `to_decide`, `decided` and `progress` are counted from the linked candidates. |
| `Sources` | `tblRxHeawvsBiAUfC` | Sources | A read-only mirror of `pipeline/sources.json`: feeds and lists the weekly harvest reads, archives the backfill agents are pointed to; access, status, reachability, how to use, quirks. Edit the file, not the table. |
| `Sidelines` | `tblUs0ZmP4x8ShWKZ` | Informal | Things seen while harvesting that do not merit a candidate (remarks, routine repeats, acts by non-claimants, cooperative steps). Tick `promote` to have the next import draft a candidate from the row. |
| `Notes` | `tblis1hiTU3E4hwPx` | Narratives | Free text across candidates: themes, precedents, cross-references to moves in the dataset, questions for Andrew Chubb; linked to candidates. |

### Candidates: the ticket 20 fields

- `flags` (multiple select, `fldFw0CeUsjumeAWa`): *Excerpt not checked · Excerpt not found · Source unreachable · Possible duplicate · Date approximate · Low confidence · Type uncertain · Needs a second source*. Set at push from the import's machine note, the date precision and the suggestion's confidence (`airtable.flags_for`); the reviewer may add or remove flags, so a refresh never rewrites them.
- `dataset_status` (single select, `fldjfYq0wvyKBygbl`): *In review → Decision recorded → Pulled into dataset → Merged → Published on site*, or *Closed without change*. Refreshed by the sync, never typed: a push sets *In review*; after `queue decide` the pull sets *Pulled into dataset*; the merge of the review PR and the next site build move it on. Until the sync does this automatically (not built), the maintainer moves them by hand or asks for it.
- `run` (link to Runs, `fldM9UtjkkVkSlAFN`): the run that produced the candidate. The REST client cannot know the Runs record id, so the link is set by the push procedure below.
- `added_on` (created time), `decided_on` (last modified time of `decision`).

## Interface pages

| Page | id | TPD Updates equivalent | What it shows |
|---|---|---|---|
| Overview | `pagAWLTLoyKhRv2Sp` | — | Numbers (to decide, decided, by decision, flagged, decided-but-not-pulled, in all), charts by claimant, type, sub-region, run and decision, the oldest undecided events; a *Runs* section (runs, still open, with problems, latest runs). |
| Queue | `pagzfbBYQDORsMZiT` | Working | Grid grouped by run; tabs *To decide · Flagged · Possible duplicates · Decided · Needs a note · Added this month*. |
| Board | `pagsOwyf3mnYRnPSz` | — | Kanban by decision. |
| Review one by one | `pag2P7Or0IlDcHTI7` | — | Record review, one candidate at a time. |
| By claimant | `pagmaJzyIH92lp7nU` | Section tabs | Tabs China · Vietnam · Philippines · Malaysia · Indonesia · Taiwan, grouped by suggested type, oldest first. |
| Hand-off | `pag9pJv7XMw68WrlV` | Hand-off | Decided candidates only; tabs *Waiting to be pulled · New moves · Merges · Duplicates and rejects · In the dataset*. The maintainer runs `pull` + `queue decide` for a run when its "Waiting to be pulled" tab is complete. |
| Run log | `pagshxM5iwYzEXtyp` | Run Log | Runs, newest first; tabs *Still open · Weekly harvests · Backfill chunks · Problems*. |
| Sources | `pagzvT7KzOaT8tLTf` | Sources | Tabs *Feeds and lists · Archives · Blocked or needs work · Open archives*. |
| Sidelines | `pagbx7NwTbhWCq5aV` | Informal | Tab *To promote*. |
| Notes | `pag4t1Whn9zE5CQCa` | Narratives | Tabs *Mine · From the runs*. |
| Candidate Detail | `pagZA6SQiPZBSV4uM` | — | The record page the others open; now also shows flags, the run, the dataset status, when the decision was made, and the notes that cite the candidate. |

Month tabs: the TPD sheet creates a tab per month; here the Queue's *Added this month* tab and the
`added_on` column do the same without new tabs. The "Read me" tab is this file.

## Pushing a run

The repository has no `AIRTABLE_TOKEN` (by decision), so records travel through the maintainer's
Airtable connector in a Claude session. From the run's branch (or a worktree of it):

```
python -m pipeline.airtable run-record --run harvest/runs/<run_id> --pr N --notes "<what to look at>" --out run.json
python -m pipeline.airtable records --run <run_id> --pr N --run-record <recXXXXXXXXXXXXXX> --out records.json
```

1. Create the `Runs` row from `run.json` (`create_records_for_table`, table `tblLK3YqY7mDL2QqW`); note the record id it returns.
2. Generate the candidate records with that id as `--run-record`, map field names to ids with
   `pipeline/airtable.json` `field_ids`, and create them in batches of at most 20 (the connector's
   comfortable size; the REST API's is 10).
3. Pull is the reverse: export the run's records (`list_records_for_table` filtered on `run_id`) to a
   file and run `python -m pipeline.airtable pull --run <run_id> --from export.json --out decisions.json`,
   then `python -m pipeline.queue decide decisions.json` on the run's branch.

Both directions are idempotent by `event_id`. `docs/backfill.md` has the whole chunk routine.

## Not done

The `dataset_status` transitions after *In review* are not automated (the sync has no token to run
with); `Sidelines` rows are not yet promoted by the import; the `Sources` mirror is refreshed by
hand when `pipeline/sources.json` changes.
