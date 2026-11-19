# 24: A continuation note extends the move it names

**What to build:** When `queue decide` applies a rejection whose note reads *continuation of X*, the move X
(a move id, or a candidate's event id once that candidate has a move) stays open through the rejected
event's year: `ongoing_through` moves forward if the year is later, and for a `coded_by = chubb` row the
change is documented in `data/corrections.csv` (`field = ongoing_through`, `reason = continuation: <event_id>
(<date>)`), as the comparability guard requires. Asked for on 2026-11-19, the first day of review: the
duration rule of the coding guide (§K) presumes a move diminished in any year without evidence of it, so
each of the ~600 continuations in the backfill would otherwise need its own edit to `moves.csv`.

**Blocked by:** 22

**Rules.** The note form is `continuation of <id>` at the start of the note (the form the pre-sort writes and
the Airtable archive confirms); anything after the id is free text. A note naming a move that does not
exist, or a move of another claimant, fails the batch (all-or-nothing, like every other invalid decision).
A note naming a candidate whose lead has no move yet is left alone and not revisited later; the coder's
note stays, and the move's duration is checked again when the year's open moves are re-read (guide §K). The
note's case and a closing stop or bracket do not matter; a note naming no known move or event fails the batch. Several continuations
of one move in a batch extend it once, to the latest year. `decide` prints and commits the count as
`extended`; the nightly apply task needs no change (its commit adds `data/`).

**Not done:** a continuation that names a candidate not yet decided is not revisited automatically;
`diminished_notes` are still written by hand; `ongoing_through_notes` is not touched.

**Status:** built 2026-11-19 (`pipeline/queue.py` pass 3, `tests/test_queue.py`).
