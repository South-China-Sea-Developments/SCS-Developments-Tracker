# Hand-compiled candidate sets

JSON lists of candidate events compiled by a person or an assistant from sources (the extractor's
output shape plus a `sources` list per event), kept here so that what was proposed is on record.
They enter the review queue with `python -m pipeline.harvest import <file> --run-id <id> --extractor "<who>"`
followed by `python -m pipeline.queue open --run harvest/runs/<id>` (ADR 0003: proposals only; a
coder decides on the review page). Each file's provenance is in `docs/sources/baselines-and-manual-candidates.md`.

| File | Compiled | By | Contents |
|---|---|---|---|
| `20261018-new-claimants-2016plus.json` | 2026-10-18 | research agents run by Claude Fable 5.1 for ticket 11 | 24 candidate events, 8 each for Malaysia, Indonesia and Taiwan, 2016–2026, each with one or two fetched sources and a verbatim excerpt |
