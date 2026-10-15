# 05: Source registry and harvester with fixtures

**What to build:** A documented source list exists, and a harvester run over a frozen folder of saved pages produces the expected set of candidate events, each with at least one source and an excerpt, without network access in tests. One manual run against live sources measures cost and yield.

**Blocked by:** 01

**Status:** ready

- [ ] A committed source registry (name, URL/feed, type, language, claimants covered, cadence, notes) covering at least: AMTI, SCSPI, Philippine Coast Guard / DFA / BFAR releases, China MFA and CCG releases, Vietnam MFA, Malaysian, Indonesian and Taiwanese agency releases, one general news feed; each entry has a tested fetcher.
- [ ] The fetcher saves raw captures with timestamp and URL; a capture folder is a valid fixture.
- [ ] The extractor turns captures into candidate events in the canonical schema with `status = candidate`, `harvest_run_id`, `extractor`, suggestions and reasoning; the prompt is built from the codebook and committed.
- [ ] Fixture test: a frozen capture folder yields an expected candidate set (fields compared, free text compared loosely); tests use a recorded-response layer so they are deterministic and offline.
- [ ] Deduplication flags candidates that match existing events by claimant, date window and location/summary similarity, without dropping them.
- [ ] One live run is executed by hand; its cost (tokens, money) and yield (candidates per source) are recorded in the ticket.
