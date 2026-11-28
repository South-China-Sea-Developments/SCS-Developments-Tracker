# Ticket 43 audit — instructions for one review job (AUDIT-20261128)

You are reviewing part of the SCS Developments Tracker's own records, unattended. Nobody will answer
questions: take the most reasonable reading of anything ambiguous, say so in your tally, and carry on.
You propose; the maintainer decides every finding later. Never edit anything under
`/home/claude/scs-developments-tracker` (no `data/`, no git). Write only the files named below. English.

## Read first (before any record)
- `/home/claude/scs-developments-tracker/docs/coding-guide.md`: §I.3 and §II.G in full, above all
  **The maintainer's binding rulings** in §II.G, which override anything else you believe about the method:
  use of force is the taking of a feature; violence against people or vessels is coercive however severe
  (e.g. CCG personnel beating fishermen, CN202406, was coded force by mistake); a claim without a threat of
  punishment is declarative however strong its words.
- `/home/claude/scs-developments-tracker/docs/codebook/chubb-2021-appendix.txt` (Chubb's methodological
  appendix): the parts on the four types, the domains, issues and dyads, and year-on-year intensification.
- Chubb's article and report, for the parts you need: `/home/claude/refs/chubb/chubb-2021-is.txt` and
  `/home/claude/refs/chubb/chubb-2022-sr99.txt` (search them; never copy them anywhere).
- `/home/claude/scs-developments-tracker/pipeline/rereview.py`, lines 60–250: the fields a finding may
  address (`MOVE_FIELDS`, `EVENT_FIELDS`), how `render` writes a current value, and how `parse` reads a
  proposal. Your `current` must be exactly what `render` gives for the record; your `proposed` must parse.

## For every record in your packets
A packet (`/tmp/audit/packets/<claimant>-<year>.json`) holds: `project_moves` (the project's moves of that
claimant-year, each with its events and their sources), `other_events` (the year's harvested events decided
otherwise: rejected, merged, or accepted into a move of another year or into a Chubb move, with `its_move`),
`reference_moves_prev_and_same_year` (the claimant's moves of the year before and the same year, the
reference for the year-on-year test) and `chubb_comparison_set` (Chubb's moves of the same type and issue
within five years, or the nearest years when Chubb's series has ended).

The records to review are the project's moves and every event in `project_moves[].events` and
`other_events`. Test each:
- **Place**: feature, coordinates, precision, sub-region (1 Tonkin, 2 Paracels, 3 central west, 4 central
  east, 5–8 Spratly NW/NE/SE/SW, 9 Nam Con Son, 10 far south); the move's sub-region flags against its events.
- **The decision** and its review note: does the accept or reject hold against the sources and the guide,
  and is it consistent with how like cases were decided elsewhere in your packets?
- **Type** (by the guide's boundaries and the binding rulings), then **domains**, **issues**, **dyads**.
- For a move: is it a year-on-year intensification against the reference moves, and by which criterion
  (novelty, frequency, scope); its **ongoing_through** year. For an event: does it belong to its move?
- **Date** and its precision; the **summary** or **description** against the sources.
- **Chubb's practice**: where Chubb coded a like act differently (in the comparison set), say which case
  and how.

Open the first source of every record with WebFetch (no curl, no web.archive.org, no mirrors); when it
cannot be reached, try the next source; judge from the excerpt only when none can be reached, and say so.
For rejected events whose note gives a plain reason (off-topic, not about the sea, a duplicate of a named
event), the excerpt and the note are enough unless something in them looks wrong.

## Findings
Write a finding **only where you would code the record differently**, one per record and field:

```
{"kind": "move"|"event", "id": "<move_id or event_id>", "field": "<one of the fields>", "current": "...",
 "proposed": "...", "reasoning": "...", "evidence": "...", "chubb": "...", "confidence": "high"|"medium"|"low"}
```
- `current` exactly as `render` writes it (type, domains, issues as comma-separated flag names in the
  schema's order; sub-regions as numbers `1, 4`; an event's date `start | end | precision`; place
  `name | lat | lon | precision | subregion`; decision = the event's status).
- `proposed` in the same form. For an event's decision: `reject`, `reconsider` (it would need a new move;
  say what move in the reasoning) or `accept into MOVE_ID`. When every event of a move should go, write one
  `withdraw` finding on the move instead (proposed `withdraw`).
- `reasoning`: the rule (quote the guide or Chubb briefly, under 15 words per quote) and how the sources meet
  it. `evidence`: the passages relied on, short, with their URLs. `chubb`: the comparable cases and how
  Chubb coded them, or "none comparable". `confidence`: high, medium or low.
- No finding for style, wording, or a difference that changes nothing in the coding.

## Output
For each packet `<claimant>-<year>` in your job:
- `/tmp/audit/findings/<claimant>-<year>.json`: a JSON list of findings (`[]` when you agree with everything).
- `/tmp/audit/findings/<claimant>-<year>.tally.json`: `{"records_reviewed": N, "moves": N, "events": N,
  "findings_by_field": {...}, "sources_unreachable": [urls], "notes": "..."}`.
Validate each findings file with python (`json.load`) before you finish. Your final answer: one line per
packet with its counts.
