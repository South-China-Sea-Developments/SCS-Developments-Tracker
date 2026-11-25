# Audit prompt (ticket 43): a deep review of every record the maintainer decided

The prompt for the unattended audit session. It is run only when the maintainer asks (ticket 43); a
scheduled task or a live session pastes it whole, with `AUDIT_ID` set (for example `AUDIT-20261215`).

---

You are auditing the SCS Developments Tracker, unattended. Nobody will answer questions: do not call
AskUserQuestion; take the most reasonable reading of anything ambiguous, say so in the report, and carry on.
Read `CLAUDE.md` first and follow it. You propose; the maintainer decides every finding in Airtable
(ADR 0003). You never change `data/` here, never commit to `main`, never `git add -A`, never edit Chubb's
moves (ADR 0001). Write in English.

## 0. Setup
- `cd /home/claude/scs-developments-tracker` (clone `South-China-Sea-Developments/SCS-Developments-Tracker`
  there if missing); `git checkout main && git pull --ff-only`; `pip install -e . -q` if needed.
- Clone the private references: `gh repo clone South-China-Sea-Developments/scs-tracker-references
  /home/claude/refs`. It holds Chubb's *International Security* article (2021) and NBR Special Report 99
  (2022), as PDF and as text.
- Read, in full and before any record: `docs/coding-guide.md` (above all §I.3 and §II.G, and the
  maintainer's binding rulings there, which override anything else you believe about the method),
  `docs/codebook/chubb-2021-appendix.txt`, the two texts in `/home/claude/refs`, `docs/spec.md`,
  `pipeline/rereview.py` (the fields a finding may address and how values are written), and
  `docs/tickets/43-deep-review.md`.
- `TODAY=$(date -u +%F)`; `mkdir -p /tmp/audit`.

## 1. The work list
With python, from `data/`: every move with `coded_by = project`, and every event with a non-empty
`extractor` and status `accepted`, `rejected` or `merged`. Group them by claimant and year. For each
claimant-year, the packet a reviewer needs:
- the year's project moves (every column) and their events (every column, with their sources from
  `data/sources.csv`: URL, title, publisher, date, excerpt);
- the year's rejected and merged events, with their review notes and sources;
- the claimant's moves of the previous year and of the same year, Chubb's and the project's (the reference
  for the year-on-year test), and Chubb's moves of the same type and issue for any claimant within five
  years (the comparison set), each with its description.
Write each packet to `/tmp/audit/packets/<claimant>-<year>.json`.

## 2. Review (subagents)
Give each packet to a `general-purpose` subagent, at most six at a time, newest years first. Give it the
packet path, the paths of the coding guide, the appendix and the two reference texts (to read the parts it
needs; the guide's §II.G and the binding rulings in full), the field list of `pipeline/rereview.py`, and
these instructions:

- For every record in the packet, test: the place (feature, coordinates, precision, sub-region; the move's
  sub-region flags); the decision and its note; the type, by the guide's boundaries and the binding rulings;
  the domains, issues and dyads; for a move, whether it is a year-on-year intensification and by which
  criterion, and its ongoing-through year; for an event, whether it belongs to its move; the date and its
  precision; the summary or description against the sources. Compare with the Chubb cases in the packet:
  where Chubb coded a like act differently, say which case and how.
- Open the first source of every record with WebFetch (no curl, no web.archive.org, no mirrors); when it
  cannot be reached, try the next source; judge from the excerpt only when none can be reached, and say so.
- Write a finding **only where you would code the record differently**, one per record and field:
  `{"kind", "id", "field", "current", "proposed", "reasoning", "evidence", "chubb", "confidence"}`.
  `current` is the record's value exactly as `pipeline/rereview.py` renders it; `proposed` is written the
  same way. `reasoning` gives the rule (quote the guide or Chubb, briefly) and how the sources meet it;
  `evidence` quotes the passages relied on, with their URLs; `chubb` names the comparable cases and their
  coding; `confidence` is high, medium or low. Do not write a finding for style, wording or a difference
  that changes nothing in the coding.
- A rejected event you would accept: propose `accept into MOVE_ID` when it belongs to an existing move,
  or `reconsider` when it would need a new move (say what that move would be in the reasoning). An accepted
  event you would reject: `reject`; when every event of a move should go, write one `withdraw` finding on
  the move instead.
- Write the findings as a JSON list to `/tmp/audit/findings/<claimant>-<year>.json` (an empty list when you
  agree with everything), and a short tally: records reviewed, findings by field, sources unreachable.

Packets whose subagent fails: run them yourself the same way.

## 3. Check and file
- Merge the findings into `harvest/audit/AUDIT_ID/findings.json`.
- `python -m pipeline.rereview rows --findings harvest/audit/AUDIT_ID/findings.json --audit AUDIT_ID
  --out harvest/audit/AUDIT_ID/batches.json`. It refuses any finding whose current value is wrong, whose
  field or value is invalid, or which touches a Chubb move: fix what is yours to fix (a mis-rendered
  current value) and re-run; list the rest in the report.
- Write `docs/notes/audit-AUDIT_ID.md`: what was reviewed and how; counts by claimant, year and field;
  the findings of high confidence, one line each; the sources that could not be reached; the refused
  findings.
- On branch `audit/AUDIT_ID`: `git add harvest/audit/AUDIT_ID docs/notes/audit-AUDIT_ID.md` (those paths
  only), commit, push, open a pull request with `gh api`, and merge it once CI passes (it changes no data:
  it files the findings so the weekly task can push them).

## 4. Push the first rows
Count the base's records as the weekly task does (part C step 1, all its tables, the Re-review table
`tblR8Lb34BDuu6KjF` included). Send as many batches of `batches.json` as fit, in order, with
`create_records_for_table` on the Re-review table, `typecast: true`, each batch exactly as printed by
`python3 -c "import json; print(json.dumps(json.load(open('harvest/audit/AUDIT_ID/batches.json'))[K], ensure_ascii=False))"`.
Record the last batch sent in `harvest/audit/AUDIT_ID/pushed.txt` and commit it the same way. The weekly
task pushes the rest as sittings free room.

## 5. Report
One message with SendUserMessage: records reviewed (moves, accepted events, rejected events), findings by
field and confidence, the claimant-years with the most findings, rows pushed and rows waiting, and the
pull request.
