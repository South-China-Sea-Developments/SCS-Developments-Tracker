# 26: Main's version of shared rows after a merge

**What to build:** `python -m pipeline.sync_data`, run after merging `main` into a run branch: each data table
is rewritten as `main` has it, plus the branch's rows whose key `main` lacks. Found on 2026-11-20 applying the
rest of CN-2016-2020: the union merge rule (`.gitattributes`) kept both versions of `CN201605` — the branch's
without a sub-region and `main`'s corrected one — and the validator refused the duplicate. Any move `main` has
corrected or extended (a continuation's `ongoing_through`) would do the same on every other run branch.

**Blocked by:** 22

**Rules.** Keys: `code`, `move_id`, `event_id`, `source_id`; corrections by (`move_id`, `field`, `new_value`,
`date`). A table that does not exist on `main` is left alone. Only rows are compared; the branch's own changes
to a row `main` also has are dropped — run branches add candidates and never edit `main`'s rows, and the apply
writes its changes after the sync.

**Status:** built 2026-11-20; in the apply task's step 2.1.
