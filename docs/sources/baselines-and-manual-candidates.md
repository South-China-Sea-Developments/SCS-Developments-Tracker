# Baselines and hand-compiled candidates

## `data/baselines/`

- `CN.md`: Andrew Chubb's own zero-baseline list, copied verbatim from the methodology appendix to Chubb (2021), Harvard Dataverse doi:10.7910/DVN/3Y7NRU, **CC0**.
- `VN.md`, `PH.md`, `MY.md`, `ID.md`, `TW.md`: compiled on 2026-10-18 by research agents run by Claude Fable 5.1 for ticket 11, one agent per claimant, under one rule: a row may be written only for an action supported by a page the agent opened, with the URL and a short verbatim quote; anything else goes under "Unverified leads". The method is the same for all five: web search for the candidate items named in the brief (and others found on the way), fetch, quote, record; pages that could not be retrieved are listed under "Sources consulted" as not retrievable. A standards review on 2026-10-18 spot-checked about forty quotes against their pages and corrected three rows (one quote paraphrased, one date wrong, one source not retrievable); the structure is held by `tests/test_baselines.py`. **Reviewed for structure and sourcing only, not yet by a historian of the dispute.** They are first drafts for the maintainer and, ideally, the original author to extend.
- Rows are actions; a few rows are explicitly labelled context (a withdrawal, a cooperative agreement, the DRV's 1958 note) because the 1970 level cannot be read without them.
- Licence: the five project documents are the project's own text and fall under the data licence still to be agreed (decision 07); the quotes are short extracts of the cited sources.

## `harvest/manual/`

- `20261018-new-claimants-2016plus.json`: 24 candidate events (8 each for Malaysia, Indonesia, Taiwan; 2016–2026) compiled on 2026-10-18 by three research agents run by Claude Fable 5.1 for ticket 11, each from one or two pages the agent fetched, with a verbatim excerpt and a suggested MATS coding with its reasoning. Imported with `pipeline.harvest import` (which re-fetches each first source and checks the excerpt) and opened as a review pull request for the coder; nothing in it is accepted by that import.

## Archival sources in the registry (`kind: archive`, ticket 12)

64 entries compiled on 2026-10-19 by three research agents run by Claude Fable 5.1, one per claimant (Malaysia, Indonesia, Taiwan), from a brief naming the kinds of source Chubb's master timeline drew on. "Verified" means the agent opened the landing or search page, or an authoritative record of it (a catalogue entry, a Crossref index entry, a library guide), and took coverage years only from what that page stated; `reachable_from_cloud` records whether the page answered from cloud egress. Candidates it could not verify (the Jakarta Post's archive start, Kemlu's treaty room, Wisma Putra's statement archive, Bernama's BLIS, MOFA's 外交年鑑, Taiwan Today's retrospectives, the China Yearbook on HathiTrust) were left out rather than guessed. A review on 2026-10-19 spot-checked fourteen pages, merged four duplicate entries and replaced query URLs with landing pages.
