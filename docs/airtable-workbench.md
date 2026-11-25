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
| `Runs` | `tblLK3YqY7mDL2QqW` | Run Log | One row per harvest or backfill run: date, type (Weekly harvest / Backfill / Manual / Catch-up), scope, verdict, documents, candidates, possible duplicates, failures, excerpts verified / unchecked / not found, review PR, extractor, unreachable sources, what to look at. `to_decide`, `decided` and `progress` are counted from the linked candidates; `archived_on` and `archive` (ticket 22) say when the run's reviewed rows left the base and where their record is. |
| `Sources` | `tblRxHeawvsBiAUfC` | Sources | A read-only mirror of `pipeline/sources.json`: feeds and lists the weekly harvest reads, archives the backfill agents are pointed to; access, status, reachability, how to use, quirks. Edit the file, not the table. Emptied on 2026-11-18 to stay under the free plan's 1,000-record cap; the registry's canonical copy is `pipeline/sources.json`, and the mirror can be re-pushed when space allows. |
| `Sidelines` | `tblUs0ZmP4x8ShWKZ` | Informal | Things seen while harvesting that do not merit a candidate (remarks, routine repeats, acts by non-claimants, cooperative steps). Tick `promote` to have the next import draft a candidate from the row. |
| `Notes` | `tblis1hiTU3E4hwPx` | Narratives | Free text across candidates: themes, precedents, cross-references to moves in the dataset, questions for Andrew Chubb; linked to candidates. |

### Candidates: the face of the table (ticket 21)

The table is laid out like the maintainer's other bases (his PLA Daily base was the reference): readable
column names (`Event ID`, `Claimant`, `Start date`, `Suggested type`, `New move: type`, `Edit: location`…
— the full map is `airtable.LABELS`), coloured select chips for the claimant (CN red · VN yellow · PH blue ·
MY green · ID orange · TW purple), the move type (declarative blue · demonstrative teal · coercive orange ·
force red), the date precision, the sub-region, the suggested domains, issues and dyads (multi-selects,
coloured by actor). The table's grid view "Time-sorted" shows these first, newest first; the maintainer
duplicates it in Airtable for other slices (group by claimant, by type) — the connector cannot create views.
Two triage columns of ticket 21, `Priority` (stars) and `Selected` (a tick), were retired on 2026-11-19:
the pre-sort, the grouping by run and the `Complete` column made them redundant. They were taken off every
page and out of `pipeline/airtable.json`; the maintainer deletes the fields in Airtable (the connector cannot).

The code keeps its internal names; `pipeline/airtable.py` translates at the wire by field id (`field_ids`
in `pipeline/airtable.json`), so a column may be renamed in the base without breaking the sync — except `Run ID`, which the filter formula selecting a run's records names. The old
text and grey-select columns were renamed `zz old …` and can be deleted in Airtable (the connector cannot
delete fields).

### Candidates: the ticket 20 fields

- `flags` (multiple select, `fldFw0CeUsjumeAWa`): *Excerpt not checked · Excerpt not found · Source unreachable · Possible duplicate · Date approximate · Low confidence · Type uncertain · Needs a second source*. Set at push from the import's machine note, the date precision and the suggestion's confidence (`airtable.flags_for`); the reviewer may add or remove flags, so a refresh never rewrites them.
- `dataset_status` (single select, `fldjfYq0wvyKBygbl`): *In review → Decision recorded → Pulled into dataset → Merged → Published on site*, or *Closed without change*. Set to *In review* when the record is created and never rewritten by a refresh. The later steps are meant to be set by the workflow (`queue decide` → *Pulled into dataset*; the merge of the review PR → *Merged*; the next site build → *Published on site*), but no sync runs with a token today, so the maintainer moves them by hand or asks for it.
- `run` (link to Runs, `fldM9UtjkkVkSlAFN`): the run that produced the candidate. The REST client cannot know the Runs record id, so the link is set by the push procedure below.
- `added_on` (created time), `decided_on` (last modified time of `decision`).

### Candidates: the ticket 23 field

`Pre-sort` (`fldlmfWHAwc09itis`): the suggested decision with its reason, filled from `harvest/presort/<run_id>.json` when `records`/`push` run with `--presort` (or the file exists beside the data); a suggestion only, and a refresh without the file leaves it as it is.

A reject with a blank `Note` on a row whose `Pre-sort` begins "continuation of X" is read by the archive as the
coder confirming the pre-sort: the decision carries the note `continuation of X (pre-sort confirmed)`
(`decisions_from_records`, 2026-11-19). A note the coder typed always wins; a blank note on any other reject
still fails `decide`.

### Candidates: the `Complete` column

`Complete` (`fldxtFtzSLOFoALEB`, formula, 2026-11-19): blank while undecided; ✓ when the row has what its
decision needs; ✗ naming what is missing (`✗ note` on a reject whose pre-sort is not a continuation, `✗ merge target`, `✗ duplicate of`,
`✗ type criterion sub-regions` on a new move missing those; a new move's year is not demanded, since `decide` defaults it to
the event's). It mirrors what `queue decide` refuses, so a sitting can be
exported once the `Incomplete` tab of the Queue page is empty. A formula costs no record and is never
synced; the pipeline does not read it. Shown second on the Queue grid and first in the "Your decision"
group of the record page.

## Interface pages

| Page | id | TPD Updates equivalent | What it shows |
|---|---|---|---|
| Overview | `pagAWLTLoyKhRv2Sp` | — | Numbers (to decide, decided, by decision, flagged, decided-but-not-pulled, in all), charts by claimant, type, sub-region, run and decision, the oldest undecided events; a *Runs* section (runs, still open, with problems, latest runs). |
| Queue | `pagzfbBYQDORsMZiT` | Working | Grid grouped by run; tabs *To decide · Flagged · Possible duplicates · Decided · Needs a note · Added this month*. |
| Board | `pagsOwyf3mnYRnPSz` | — | Kanban by decision. |
| Review one by one | `pagMBrGwofJENJ3o6` | — | Record review, one candidate at a time; tabs *To decide · Flagged · Possible duplicates · Selected · Decided* (rebuilt for ticket 21; the connector cannot edit a record-review page, so its *Selected* tab and the two retired columns in its detail list are the maintainer's to remove). |
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

`Previous year's moves` lists every move of the claimant open through the previous year (coded in or before
it, ongoing through it or later), newest first, each with `through <year>` and its description cut to 160
characters (2026-11-20; the review page shows the same list in full). Generate records only from a run branch
with `main` merged in, so the lists reflect the moves accepted since the branch was cut (`.gitattributes` gives
`data/*.csv` the union merge rule, since the branch and `main` both append rows; a clone whose branch predates the
rule gets it from `.git/info/attributes`, as the apply task does). Union keeps *both* versions of a row that
changed on both sides, so after the merge run `python -m pipeline.sync_data`, which keeps main's version of
every shared row and the branch's own new rows (ticket 26).

The weekly apply task refreshes both move lists on the rows still in the base (`context-diff` builds the connector
updates for the rows whose lists differ from today's `records`; `context-check` verifies afterwards), so a
move accepted or extended in one sitting is on the cards after the next run. No other context column is rewritten.

Every new row goes out with `Reviewer` already set to the `reviewer` of `pipeline/airtable.json`
("Angelo": one coder, decision 07), so the coder never types the name; `--reviewer` overrides it for a
sitting by someone else, and `--reviewer ""` leaves the column blank. A refresh never touches it, like the
other coder fields, so a name retyped on a row stands. On 2026-11-19 the column was filled on the 862 rows
already in the base.

1. Create the `Runs` row from `run.json` (`create_records_for_table`, table `tblLK3YqY7mDL2QqW`); note the record id it returns.
2. Generate the candidate records with that id as `--run-record`, map field names to ids with
   `pipeline/airtable.json` `field_ids` (the Candidates table only; the `Runs` row is sent by field name, its
   table id is `runs_table_id` in the same file), and create them in batches of at most 20 (the connector's
   comfortable size; the REST API's is 10).
3. Pull is the reverse: export the run's records (`list_records_for_table` filtered on `run_id`) to a
   file and run `python -m pipeline.airtable pull --run <run_id> --from export.json --out decisions.json`,
   then `python -m pipeline.queue decide decisions.json` on the run's branch.

Both directions are idempotent by `event_id`. `docs/backfill.md` has the whole chunk routine.

## After review: archive and clear (ticket 22, ADR 0005)

An Airtable row is transient: it leaves the base once its decision is applied to the files, and what the
coder typed is filed in the repository first, so the free plan's cap of 1,000 records per base stops
mattering. Undecided rows stay. From the run's branch (`harvest/<run_id>`):

1. **Export** the run's rows: `list_records_for_table` on `Candidates` filtered on the run (`{Run ID} = '<run_id>'`),
   all fields, saved as JSON (`{"records": [...]}` or a bare list; labels, field ids or internal names all work).
2. **Archive:** `python -m pipeline.airtable archive --run <run_id> --from export.json` (signed by `--reviewer`,
   else the one name the rows carry, else the configured `reviewer`) writes
   `harvest/airtable/<run_id>/records.json` (every exported row, merged by event id with earlier sittings),
   `decisions.json` (the decided rows, in the shape `queue decide` reads) and `clear.json` (their Airtable ids).
3. **Apply:** `python -m pipeline.queue decide harvest/airtable/<run_id>/decisions.json`; commit the three
   archive files with the decisions on the run's branch; the review pull request carries both.
4. **Clear:** `delete_records_for_table` on `Candidates` with the `record_ids` of `clear.json`, in batches of ten,
   only after the decisions are committed and pushed. Then set `archived_on` (today) and `archive`
   (`https://github.com/<org>/<repo>/tree/main/harvest/airtable/<run_id>`, live once the pull request merges) on the run's `Runs` row
   (fields `Archived on` `fldQhcqhMo8wh3vRE`, `Archive` `fldTQRu3M4aA8fT5W`).
5. A run reviewed in several sittings repeats 1–4; `records.json` accumulates, `decisions.json` and `clear.json`
   describe the latest sitting only, and a row whose decision was archived in an earlier sitting (a failed or
   partial clear) is left out of `decisions.json`, so `decide` is never asked to re-apply it.

Since 2026-11-19 the scheduled apply task (weekly, Mondays 01:35, since 2026-11-20; *Run now* in the app for a sitting that should go out sooner) runs steps 1–4 for every run with rows marked ✓ in `Complete` and
merges the review pull request (decision 07 as amended; prompt in `docs/apply-task-prompt.md`). A row marked ✗,
and a merge whose lead is not yet decided, wait for the next run.

**One sitting, one branch (since 2026-11-25).** Steps 1–3 for every run at once:
`python -m pipeline.airtable sitting --exports <folder of <run_id>.json exports> --report report.json` cuts
`sitting/<date>` from `origin/main`, merges in the review branch of each run whose candidates are not on main
yet, holds back merges whose lead is undecided, archives and applies run by run (a refused run is undone and
reported), validates and commits. One pull request then carries the whole sitting, and a data-only pull
request gets CI's light check (about five minutes) instead of the full suite. Once it merges, close the folded
runs' review pull requests and clear the rows listed under `clear`. Applying run by run on each review branch
meant one CI cycle per run, each repeated after the previous merge conflicted: an hour and a half for six runs
on 2026-11-25.

With a token, `clear --run <run_id>` deletes a whole run's rows but archives nothing: run `archive` first.

## The Re-review table (ticket 43)

`Re-review` (`tblR8Lb34BDuu6KjF`) holds the audit's disagreements with records already decided: one row
per record and field, with *Current*, *Proposed*, *Reasoning*, *Evidence* (source passages) and *Chubb
comparison*. Answer *Decision*: **keep** (the current coding stands), **take** (the proposal) or **edit**
(your own value in *Your value*, written as *Current* is: a type name, comma-separated flags, sub-region
numbers, `name | lat | lon | precision | subregion` for a place, `start | end | precision` for a date).
*Your note* is optional and goes into the record's review note.

`python -m pipeline.rereview rows` builds the rows from an audit's findings; `python -m pipeline.rereview
apply --from <export.json>` applies the decided rows to `data/`, archives them under
`harvest/airtable/rereview/` and writes `clear.json`. A row whose record changed after the finding was made
is skipped and stays. The weekly task applies decided rows and pushes waiting ones as room frees.
The rows count toward the base's 1,000-record cap.

## Not done

The `dataset_status` transitions after *In review* are not automated (the sync has no token to run
with); `Sidelines` rows are not yet promoted by the import; the `Sources` mirror is refreshed by
hand when `pipeline/sources.json` changes.
