# 23: The pre-sort

**What to build:** For every candidate of a review run, a suggestion of what the coder's decision is likely
to be — *continuation of move X*, *same move as candidate Y*, *new move (criterion)*, *duplicate of event Z*,
or *unclear* — with a reason, so the coder confirms or overrides rather than constructs. A suggestion
layer like `suggested_type` (ADR 0003: machines propose, humans decide); nothing enters the files until
`queue decide` applies the coder's decisions. Asked for on 2026-11-17 to shorten the review of 1,300
candidates.

**Blocked by:** 06, 19

**Status:** built 2026-11-17; pre-sorts compiled for the 27 open runs the same day.

- [x] `pipeline/presort.py`: the file shape (`harvest/presort/<run_id>.json`), `context` (the candidates with
  source titles, the claimant's accepted moves of the previous and same year and those ongoing into the
  previous year, the baseline for a 1970 year), `check` (every candidate covered once; dispositions known;
  `of` resolves to a move of the claimant, a candidate of the run or an event; a criterion on every
  `new_move`), `label`. Tests in `tests/test_presort.py`.
- [x] `queue page` reads `harvest/presort/<run_id>.json` when it exists (or `--presort FILE`): a pill and a
  "Pre-sort" paragraph on each card; the form is prefilled from it where the coder has no saved draft
  (continuation → reject with the note "continuation of <move_id>"; same_move → merge into that
  candidate's move; new_move → the criterion; duplicate → the event).
- [x] Airtable: `Pre-sort` (`fldlmfWHAwc09itis`) on `Candidates`; `records`/`push` take `--presort` and fill it.
- [x] The pre-sorts themselves: one Opus agent per claimant, working period by period from the earliest, with
  the previous period's candidate set as "last year's record" where no moves are coded yet; `presorted_by`
  names the model. Files committed on main; each run's review page regenerated on its branch.

**Not done.** The pre-sort is not compared with the decisions in the agreement report (the report's unit is
the move's coding, not the disposition); a `disposition` row in that report would be a small addition once
the first decided run exists. For 2016 onward of a claimant whose previous year is itself undecided
candidates, the pre-sorter reasons from those candidates, so its "continuation" calls are provisional until
that year is decided.
