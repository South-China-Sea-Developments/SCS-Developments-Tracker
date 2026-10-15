# 0003. Automation boundary: machines harvest and propose, humans decide

Date: 2026-10-15. Status: accepted.

## Context

Chubb's method has three jobs: (1) harvest every plausibly relevant development into a master timeline; (2) judge which developments constitute a year-on-year intensification by a claimant (a move) rather than a continuation; (3) code the move's Type, Domain, Issue, Sub-region, Dyad and Ongoing-through. Job 1 was the bottleneck (seven years of timeline-building). Jobs 2 and 3 are judgments; human inter-coder agreement on job 3 was 87–92 %.

## Decision

Scheduled runs **harvest** a fixed, documented source list and **extract candidate events** (date, actor, place, what happened, source) into a review queue. For each candidate the system may attach a **suggested** grouping into a move and a **suggested** MATS coding with its reasoning. A human coder accepts, edits or rejects; **only accepted events and moves enter the dataset**, and the dataset records who accepted them.

Every suggestion is stored alongside the final human coding, so machine–human agreement can be measured the same way Chubb measured his coders.

## Alternatives considered

- **Store only** (humans do all three jobs; the system is a database and a site). Rejected: leaves the bottleneck in place and offers nothing a spreadsheet does not.
- **Code automatically, humans audit a sample.** Rejected: the two judgments that define the dataset would be made by a model whose agreement with the codebook is unmeasured; the result could not be presented as a continuation of MATS.

## Consequences

- The events table has a lifecycle state (candidate → accepted / rejected / merged) and provenance fields (source run, model, suggestion, reviewer, decision date).
- The review queue is a first-class part of the system, not an afterthought; its usability determines throughput.
- The same harvester serves the 1970–2015 backfill for new claimants by running over archival sources instead of live feeds.
- If measured agreement ever justifies delegating part of job 2 or 3 to the machine, that is a new ADR.
