# Decision map

The open decisions between here and a working, automatically updated database, one file each, with the decisions that must be settled first. Settled decisions record the answer and date. Decisions that are hard to reverse also get an ADR in `docs/adr/`.

| # | Decision | Depends on | Status |
|---|---|---|---|
| 01 | Coding scheme fidelity | — | settled → ADR 0001 |
| 02 | Unit of analysis for new data | 01 | settled → ADR 0002 |
| 03 | Claimant scope | 01 | settled |
| 04 | Collection method and the automation boundary | 01, 02 | open |
| 05 | Canonical storage | 04 | open |
| 06 | Public front end | 05 | open |
| 07 | Governance: licence, versioning, attribution, author relationship | 01 | open |
| 08 | Operations: where scheduled runs happen, who maintains | 04, 05 | open |
