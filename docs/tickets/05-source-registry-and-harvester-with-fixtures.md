# 05: Source registry and harvester with fixtures

**What to build:** A documented source list exists, and a harvester run over a frozen folder of saved pages produces the expected set of candidate events, each with at least one source and an excerpt, without network access in tests. One manual run against live sources measures cost and yield.

**Blocked by:** 01

**Status:** done except the live run (2026-10-15, PR #5); the live run waits for the `ANTHROPIC_API_KEY` repository secret

- [x] A committed source registry (name, URL/feed, type, language, claimants covered, cadence, notes) covering at least: AMTI, SCSPI, Philippine Coast Guard / DFA / BFAR releases, China MFA and CCG releases, Vietnam MFA, Malaysian, Indonesian and Taiwanese agency releases, one general news feed; each entry has a tested fetcher. *The two fetch paths (feeds, listing pages) are tested against a local server; per-entry link patterns were exercised in a live trial fetch, not in tests. Reachability from cloud egress on 2026-10-15: the Philippine government sites (PCG, DFA, BFAR) and the China Coast Guard site refuse or reset connections and are registered as `blocked_from_cloud`; Kemlu's listing is script-rendered (`needs_work`). Philippine and Indonesian coverage comes meanwhile from news searches. Google News items yield the headline and source only; resolving them to the publisher article is a follow-up.*
- [x] The fetcher saves raw captures with timestamp and URL; a capture folder is a valid fixture.
- [x] The extractor turns captures into candidate events in the canonical schema with `status = candidate`, `harvest_run_id`, `extractor`, suggestions and reasoning; the prompt is built from the codebook and committed.
- [x] Fixture test: a frozen capture folder yields an expected candidate set (fields compared, free text compared loosely); tests use a recorded-response layer so they are deterministic and offline. *The seven fixture captures are real documents; the recordings were written by hand to stand for a careful extractor until the first live run (`--record`) replaces them. Structured fields are compared exactly; free text is checked for presence and length only.*
- [x] Deduplication flags candidates that match existing events by claimant, date window and location/summary similarity, without dropping them.
- [ ] One live run is executed by hand; its cost (tokens, money) and yield (candidates per source) are recorded in the ticket. *Blocked on the `ANTHROPIC_API_KEY` repository secret; the "harvest" workflow (ticket 07) is ready to run by hand or on its Monday schedule. A trial fetch on 2026-10-15 captured 111 documents from 13 active sources in about four minutes.*
