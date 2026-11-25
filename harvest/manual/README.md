# Hand-compiled candidate sets

JSON lists of candidate events compiled by a person or an assistant from sources (the extractor's
output shape plus a `sources` list per event), kept here so that what was proposed is on record.
They enter the review queue with `python -m pipeline.harvest import <file> --run-id <id> --extractor "<who>"`
followed by `python -m pipeline.queue open --run harvest/runs/<id>` (ADR 0003: proposals only; a
coder decides on the review page). Each file's provenance is in `docs/sources/baselines-and-manual-candidates.md`.

What a set's compiler could not compile is recorded in the single register `docs/notes/backfill-gaps.md` (per claimant, chronological).

| File | Compiled | By | Contents |
|---|---|---|---|
| `20261018-new-claimants-2016plus.json` | 2026-10-18 | research agents run by Claude Fable 5.1 for ticket 11 | 24 candidate events, 8 each for Malaysia, Indonesia and Taiwan, 2016–2026, each with one or two fetched sources and a verbatim excerpt |
| `20261107-PH-2016-2020.json` | 2026-11-07 | a research agent run by Claude Fable 5.1 for ticket 19, briefed by `BRIEF.md` | 80 candidate events, the Philippines 2016–2020, each with one or two opened sources and a verbatim excerpt |
| `20261107-MY-2016-2020.json` | 2026-11-09 | a research agent run by Claude Fable 5.1 for ticket 19, briefed by `BRIEF.md` | 40 candidate events, Malaysia 2016–2020 |
| `20261107-CN-2016-2020.json` | 2026-11-09 | a research agent run by Claude Fable 5.1 for ticket 19, briefed by `BRIEF.md` | 93 candidate events, China 2016–2020 |
| `20261107-VN-2016-2020.json` | 2026-11-09 | a research agent run by Claude Fable 5.1 for ticket 19, briefed by `BRIEF.md` | 107 candidate events, VN 2016–2020 |
| `20261107-ID-2016-2020.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 41 candidate events, ID 2016–2020 |
| `20261107-TW-2016-2020.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 58 candidate events, TW 2016–2020 |
| `20261107-MY-1970s.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 8 candidate events, MY 1970s |
| `20261107-MY-1980s.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 32 candidate events, MY 1980s |
| `20261107-MY-1990s.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 29 candidate events, MY 1990s |
| `20261107-MY-2000s.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 28 candidate events, MY 2000s |
| `20261107-MY-2010-2015.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 31 candidate events, MY 2010–2015 |
| `20261107-MY-2021-2026.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 43 candidate events, MY 2021–Oct 2026 |
| `20261107-ID-1970s.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 18 candidate events, ID 1970s |
| `20261107-ID-1980s.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 12 candidate events, ID 1980s |
| `20261107-ID-1990s.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 27 candidate events, ID 1990s |
| `20261107-ID-2000s.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 27 candidate events, ID 2000s |
| `20261107-ID-2010-2015.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 55 candidate events, ID 2010–2015 |
| `20261107-ID-2021-2026.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 30 candidate events, ID 2021–Oct 2026 |
| `20261107-TW-1970s.json` | 2026-11-16 | a research agent for ticket 19, briefed by `BRIEF.md` | 22 candidate events, TW 1970s |
| `20261107-TW-1980s.json` | 2026-11-17 | a research agent for ticket 19, briefed by `BRIEF.md` | 11 candidate events, TW 1980s |
| `20261107-TW-1990s.json` | 2026-11-17 | a research agent for ticket 19, briefed by `BRIEF.md` | 32 candidate events, TW 1990s |
| `20261107-TW-2000s.json` | 2026-11-17 | a research agent for ticket 19, briefed by `BRIEF.md` | 38 candidate events, TW 2000s |
| `20261107-TW-2010-2015.json` | 2026-11-17 | a research agent for ticket 19, briefed by `BRIEF.md` | 41 candidate events, TW 2010–2015 |
| `20261107-TW-2021-2026.json` | 2026-11-17 | a research agent for ticket 19, briefed by `BRIEF.md` | 57 candidate events, TW 2021–Oct 2026 |
| `20261107-CN-2021-2026.json` | 2026-11-17 | a research agent for ticket 19, briefed by `BRIEF.md` | 118 candidate events, CN 2021–Oct 2026 |
| `20261107-VN-2021-2026.json` | 2026-11-17 | a research agent for ticket 19, briefed by `BRIEF.md` | 103 candidate events, VN 2021–Oct 2026 |
| `20261107-PH-2021-2026.json` | 2026-11-17 | a research agent for ticket 19, briefed by `BRIEF.md` | 119 candidate events, PH 2021–Oct 2026 |
| `20261124-GAPS.json` | 2026-11-24 | six research agents run by Claude Opus 5.5 for the gaps register, briefed by `BRIEF.md` | 61 candidate events (CN 19, ID 18, TW 9, PH 6, MY 5, VN 4): Chinese acts against Vietnam, Malaysia and Indonesia 2025–Oct 2026 and the responses, plus 37 register ◆ entries |
