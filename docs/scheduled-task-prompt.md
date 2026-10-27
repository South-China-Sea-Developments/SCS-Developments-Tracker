# The weekly scheduled task's prompt

The Claude-app scheduled task "SCS Tracker weekly harvest" (created 2026-10-26; `CRON_TZ=America/New_York 17 2 * * 1`, automatic approval, push notifications on) sends the text below at every firing. It is recorded here verbatim so the task can be recreated on any account (`docs/handoff.md`). Keep this file and the live task in step: when one changes, change the other.

---

You are running the weekly harvest of the SCS Developments Tracker, unattended. Nobody will answer questions: do not call AskUserQuestion; take the most reasonable reading of anything ambiguous, say so in your final report, and continue. The maintainer is Angelo M. (GitHub `Angelo-M-SCS`; organisation `South-China-Sea-Developments`, repository `SCS-Developments-Tracker`). This run is the "session route" of docs/tickets/14-extraction-on-the-subscription.md, scheduled (docs/decisions/08-operations.md, amendment of 2026-10-26): you fetch the registered sources, you yourself answer the extraction prompts, the pipeline turns the answers into candidate events, and a review pull request is opened for the maintainer. You decide nothing about the dataset (ADR 0003): every candidate goes to him; you never merge, never commit to `main`, never edit `data/` by hand, never run `queue decide`.

## 0. Environment
- Repository: `/home/claude/scs-developments-tracker`. If the folder is missing, `gh repo clone South-China-Sea-Developments/SCS-Developments-Tracker /home/claude/scs-developments-tracker`. Then `cd` there, `git checkout main && git pull --ff-only origin main`, `git status` must be clean (if not, `git stash -u` and note it).
- Python 3.12+ with the project installed: `pip install -e . -q` if `python -m pipeline.validate --help` fails.
- `gh` is authenticated as the maintainer; GitHub pushes go to branches only.
- Read first: README.md section "Extraction without an API key", and `.claude/skills/harvest-extract/SKILL.md` (the skill you will follow in step 4). If the `harvest-extract` skill is listed in your available skills, you may invoke it with the Skill tool; otherwise follow SKILL.md by hand.
- `RUN_ID=$(date -u +%Y%m%dT%H%M)`; use it everywhere below. `MODEL` = the model id you are running as (for example `claude-fable-5-1`); the answer string is `claude-session/$MODEL`.

## 1. State and fetch
```
python -m pipeline.ops state pull
python -m pipeline.harvest probe || true
python -m pipeline.harvest fetch --out harvest/captures/$RUN_ID --state harvest/state.json
```
If fetch exits non-zero ("every active source failed"), go to step 8 (failure).

## 2. Prompts
```
python -m pipeline.harvest prompts --captures harvest/captures/$RUN_ID --out harvest/prompts/$RUN_ID --max-documents 80 --answered-by claude-session/$MODEL
```
Note the counts it prints (documents, prompts, not about the sea, deferred). If 0 prompts were written, skip to step 6 with no candidates.

## 3–4. Answer the prompts (the skill)
Follow `.claude/skills/harvest-extract/SKILL.md` exactly for run `$RUN_ID`: `system.md` once, batches of about eight prompts per subagent, each answer written to `harvest/recordings/$RUN_ID/<key>.json` as `{"model": "claude-session/$MODEL", "text": {"events": [...]}, "stop_reason": "end_turn"}` with `model` copied verbatim from `index.json` `answer_format.model`. When all batches are done, compare the answer files with `index.json` and answer any missing prompt yourself. Touch nothing outside `harvest/recordings/$RUN_ID/`.

## 5. Extract and open the review pull request
```
python -m pipeline.harvest extract --captures harvest/captures/$RUN_ID --out harvest/runs/$RUN_ID --prompts harvest/prompts/$RUN_ID --recordings harvest/recordings/$RUN_ID --run-id $RUN_ID
git config user.name "Angelo-M-SCS" ; git config user.email "$(gh api user --jq .email 2>/dev/null || echo 'noreply@github.com')"
python -m pipeline.queue open --run harvest/runs/$RUN_ID
```
`queue open` creates branch `harvest/$RUN_ID`, commits the candidates and the review page, pushes, and opens the pull request (it prints the number). With zero candidates it prints "no candidates; nothing to review" and that is a valid outcome. Afterwards `git checkout main`.

## 6. Save the state, housekeeping
```
python -m pipeline.ops state push --run-id $RUN_ID --report harvest/runs/$RUN_ID/run.json --captures harvest/captures/$RUN_ID
python -m pipeline.ops failure-issue --resolved --run-id $RUN_ID --run-url "https://claude.ai/code (scheduled session, run $RUN_ID)"
python -m pipeline.ops remind --maintainer Angelo-M-SCS --days 7
```
Deferred documents (over the 80 cap) are retried next week by the state mechanism; that is expected.

## 7. Report
End with a short report: run id; documents fetched per source (from `harvest/captures/$RUN_ID/fetch-report.json`); prompts written / not about the sea / deferred; answers written; candidates and possible duplicates (from `harvest/runs/$RUN_ID/run.json`), failures with their errors; the pull request number and branch, or "no candidates"; whether the state was pushed; anything odd (sources that failed, prompts you could not answer, the stash from step 0). Nothing else needs doing: the maintainer reviews the pull request himself.

## 8. Failure
If any step fails in a way you cannot repair in one retry: do not push the state; run `python -m pipeline.ops failure-issue --run-id $RUN_ID --run-url "https://claude.ai/code (scheduled session, run $RUN_ID)" --status failed --detail "<what failed, the command and its last lines of output>"`, then write the report with the failure at the top.

Rules: no AskUserQuestion, no push notifications; do not edit `pipeline/`, `web/`, `docs/` or `data/`; do not merge anything; do not create or change scheduled tasks; if the maintainer's instruction in decision 07 (no project-coded entry merged until he reviews it himself) ever seems to conflict with a step, the step that stops is the merge, which you never do anyway.
