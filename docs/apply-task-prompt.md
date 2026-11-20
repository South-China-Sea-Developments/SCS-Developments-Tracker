# The nightly apply task's prompt

The Claude-app scheduled task "SCS Tracker nightly apply" (created 2026-11-19, prompt revised 2026-11-20; `CRON_TZ=America/New_York 35 1 * * *`,
push notifications on) sends the text below at every firing. It carries the maintainer's Airtable decisions into
the dataset and merges them (decision 07, amendment of 2026-11-19). Recorded here verbatim so the task can be
recreated on any account (`docs/handoff.md`). Keep this file and the live task in step: when one changes, change
the other.

---

You are applying the maintainer's review decisions to the SCS Developments Tracker, unattended. Nobody will
answer questions: do not call AskUserQuestion; take the most reasonable reading of anything ambiguous, say so
in your final report, and continue. The maintainer is Angelo M. (GitHub `Angelo-M-SCS`; organisation
`South-China-Sea-Developments`, repository `SCS-Developments-Tracker`). Decision 07 (amended 2026-11-19): a
decision the maintainer recorded in Airtable *is* his review; your job is to file it, apply it, and merge the
run's review pull request once the pipeline and CI accept it. You decide nothing about the dataset yourself:
you never change a decision, never fill in a blank, never edit `data/` by hand, never commit to `main` directly,
never `git add -A`. Read `docs/airtable-workbench.md` ("After review: archive and clear") before starting.

## 0. Environment
- Repository `/home/claude/scs-developments-tracker` (clone it with `gh repo clone South-China-Sea-Developments/SCS-Developments-Tracker /home/claude/scs-developments-tracker` if missing). `cd` there; `git fetch origin`; `git checkout main && git pull --ff-only origin main`; `git status` must be clean (otherwise `git stash -u` and note it).
- `pip install -e . -q` if `python -m pipeline.validate --help` fails.
- Airtable: base `appK9OckCTV15vQwx`, Candidates `tbl1jZACWLq6FXPOq`, Runs `tblLK3YqY7mDL2QqW`, through the Airtable connector tools (load their schemas with ToolSearch first: `list_records_for_table`, `delete_records_for_table`, `update_records_for_table`). Field ids on Candidates: run_id `fldZINTpPC0Ic2DSG`, event_id `fldYslClcFl43XHsR`, Decision `fldnmdasrI25UhMZk` (choice `undecided` = `selUlBV77rBPmsbZn`), Complete `fldxtFtzSLOFoALEB`. On Runs: run_id `fldq1sABT2lMtHj7p`, Archived on `fldQhcqhMo8wh3vRE`, Archive `fldTQRu3M4aA8fT5W`.
- `TODAY=$(date -u +%F)`.

## 1. Which runs have decisions ready
`list_records_for_table` on Candidates, `fieldIds` [run_id, event_id, Decision, Complete], filter: Decision `!=` `selUlBV77rBPmsbZn` AND Complete `=` `✓`, `pageSize` 1000. Group the result by run_id. Rows with Complete `✗` are the maintainer's to fix: leave them, list them in the report. If nothing is ready, report "nothing to apply" and stop.

## 2. For each run R with ready rows, in turn
1. **Branch:** `git checkout -B harvest/R origin/harvest/R` (if the branch does not exist on the remote, skip the run and report it), then `git merge --no-edit origin/main` so the branch carries the current pipeline (run branches are cut weeks before they are applied; on 2026-11-20 the first run failed at step 4 for want of this). If the merge conflicts, `git merge --abort`, skip the run and report it.
2. **Export** the ready rows: `list_records_for_table` on Candidates, all fields (no `fieldIds`), filter run_id `=` R AND Decision `!=` undecided AND Complete `=` `✓`, `pageSize` 50, following `nextCursor` until exhausted. Save every page's `records` array to `harvest/airtable/R/export-page-N.json` with the Write tool (when a tool result was saved to a file because it was large, copy that file instead of retyping it; never retype record contents by hand). Then merge: `python - <<'EOF'` → read all `export-page-*.json`, concatenate the `records` arrays, write `harvest/airtable/R/export.json` as `{"records": [...]}`, delete the page files.
3. **Hold back merges whose lead is not in this export** (a merge into a candidate needs its lead decided `new_move` in the same batch): with `pipeline.airtable.normalise_record(r, load_config()["field_ids"])` on each record, drop any record whose `decision` is `merge` and whose `merge_into_candidate` is set but is not the `event_id` of an exported record decided `new_move`; write the rest back to `export.json`; list the held-back event ids for the report.
4. **Archive:** `python -m pipeline.airtable archive --run R --from harvest/airtable/R/export.json --date $TODAY` (exit 1 with "no row" means nothing left after step 3: skip the run; any other failure is reported verbatim, never as "nothing to apply").
5. **Apply:** `python -m pipeline.queue decide harvest/airtable/R/decisions.json --no-commit --date $TODAY`. If it exits non-zero: `git checkout -- data harvest/airtable/R`, `rm -f harvest/airtable/R/decisions.json harvest/airtable/R/clear.json`, record the error verbatim, and go to the next run. Nothing of this run is cleared from Airtable.
6. **Validate:** `python -m pipeline.validate` must pass; otherwise treat as step 5's failure.
7. **Commit and push:** `git add data harvest/airtable/R` (named paths only); commit with the message `Apply the maintainer's decisions for R (sitting of $TODAY)` and a body giving the counts `decide` printed; end the message with the attribution lines the system gave you; `git push origin harvest/R`.
8. **Merge:** find the run's review pull request: `gh api "repos/South-China-Sea-Developments/SCS-Developments-Tracker/pulls?head=South-China-Sea-Developments:harvest/R&state=open" --jq '.[0].number'`. Poll `gh api repos/.../commits/harvest/R/check-runs --jq '.check_runs[]|"\(.name) \(.status) \(.conclusion)"'` every 20 s for up to 10 minutes until `validate` is `completed`. If `success`: `gh api -X PUT repos/.../pulls/N/merge -f merge_method=squash -f commit_title="Apply the maintainer's decisions for R (#N)"` — do not append anything else to the title. If it failed or no pull request exists: do not merge, do not clear; report. (`gh pr` subcommands do not work through the proxy; use `gh api`.)
9. **Clear**, only after the merge succeeded: `delete_records_for_table` on Candidates with the `record_ids` of `harvest/airtable/R/clear.json`, at most 10 ids per call. Then on the Runs row whose run_id is R (`list_records_for_table` on Runs, filter run_id `=` R): `update_records_for_table` setting Archived on = `$TODAY`, Archive = `https://github.com/South-China-Sea-Developments/SCS-Developments-Tracker/tree/main/harvest/airtable/R`. If the Runs row does not exist, say so in the report and go on.
10. `git checkout main && git pull --ff-only origin main` before the next run.

## 3. Report
Send one message with SendUserMessage (load it with ToolSearch): per run, the counts (new moves, merges, duplicates, rejects), the pull request merged, the rows cleared, the held-back merges and the `✗` rows left for the maintainer; any run skipped and why, with the error text. Then the one-line reminder that the site rebuilds from `main` within minutes. No other output is needed.
