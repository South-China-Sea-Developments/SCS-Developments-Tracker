# Brief for compiling a hand-compiled candidate set

The instruction given to each research agent that compiles a chunk's master timeline (ticket 19).
It is kept here so the method behind every `harvest/manual/*.json` file is on record. The agent
proposes; the maintainer decides every candidate on the review page (ADR 0003).

## The task

Compile every dated incident in which **one claimant** asserted its South China Sea claim in a
**non-cooperative** way during **one period**, as a JSON list in the shape below, from sources you
have actually opened, with a verbatim excerpt from each. This is the raw material for Andrew
Chubb's Maritime Assertiveness Time Series (MATS) coding; you are not coding moves, you are listing
the dated events a coder will judge.

## What counts as an event

A single dated act by the claimant state (its government, forces, agencies, state companies or
state-sanctioned activity) that asserts its claim: a statement, protest, note verbale or law; a
patrol, survey, construction, resource activity (drilling, fishing enforcement, licensing),
administrative act (naming, zoning, legislation, court proceedings), state-sanctioned tourism or
activism; interference with another state's vessels or aircraft, detentions, warning shots,
economic or diplomatic punishment; use of force or seizure of a feature. Only the claimant's own
behaviour. Cooperative or conciliatory acts (joint patrols, agreements, consultations) are not
events. Acts by non-claimants (the United States, Japan, Australia, India) are not events.

Include an act only when a source gives a date to at least the month, and says what the claimant
did and, where possible, where. Prefer incidents that could matter to a coder judging whether the
year is a step up on the year before: something **new** for that claimant, something done **more
often** than before, or something of **wider scope** (a new area, a new kind of target). Routine
repeats of an established practice can be summarised as one event per year with the frequency
stated in the summary ("fifth such patrol of the year").

## Sources

Open the sources and quote them. Use, in this order of preference: primary sources (government
statements, laws, UN deposits, parliamentary records, official chronologies); the archival sources
listed for the claimant in `pipeline/sources.json` (`python -m pipeline.harvest archives`), where
reachable; established trackers and chronologies (CSIS AMTI, the Australian Parliamentary Library
chronology, IISS, Reuters, AP, regional press); scholarly chronologies. Wikipedia and similar may
guide you to sources but are not themselves sources. One source per event is required, two are
better when they disagree on a date or detail.

Each `excerpt` must be copied **verbatim** from the fetched page — the same characters, at most
400 — because the importer re-fetches the first source and checks that the excerpt occurs in it.
Pick a short, distinctive sentence or clause; do not paraphrase, fix typos or join fragments. If
the only source is a PDF or a paywalled page, say so in `reasoning` (the importer records that
the excerpt was not checked).

## Output

A JSON list, one object per event, written to the path you are given. Fields:

```
claimant          CN | VN | PH | MY | ID | TW
date_start        YYYY-MM-DD (first of the month or year when only that is known)
date_end          YYYY-MM-DD (same as date_start for a single day)
date_precision    day | month | year
location_name     the named feature or area as the source gives it, or ""
subregion         "1".."10" when confident (1 Gulf of Tonkin; 2 Paracels; 3 Central-West; 4 Central-East incl. Scarborough;
                  5 Spratly NW incl. Thitu, Subi; 6 Spratly NE incl. Second Thomas, Mischief, Reed Bank; 7 Spratly SE incl.
                  Commodore, Swallow Reef; 8 Spratly SW incl. Spratly Island, Fiery Cross; 9 Nam Con Son incl. Vanguard Bank;
                  10 Far South incl. James Shoal, Luconia, Natuna waters), else ""
summary           one or two sentences in English, past tense, what happened, who did it, to whom; no speculation
actors            the units or agencies named, or ""
suggested_type    declarative | demonstrative | coercive | force (Chubb's definitions: declarative = verbal assertions, protests,
                  legislation; demonstrative = unilateral administration without confrontation: patrols, surveys, construction,
                  resource development, tourism, domestic judicial acts; coercive = threat or imposition of punishment: warnings,
                  diplomatic/economic punishment, warning shots, physical interference; force = military force or seizure)
suggested_domains subset of ["domestic", "diplomatic", "physical"]
suggested_issues  subset of ["military", "administrative", "energy", "fisheries", "politics"]
suggested_dyads   list of two-letter codes, actor first: C China, V Vietnam, P Philippines, M Malaysia, B Brunei, I Indonesia,
                  R Taiwan, A all states, U unclear — e.g. ["CP"]
reasoning         one or two sentences: why this is an event and why that type
confidence        high | medium | low
sources           list of {url, title, publisher, pub_date (YYYY-MM-DD or ""), language, excerpt}; the first is the one checked
```

Order the list by date. Do not invent dates, places or details that are not in the text. Do not
commit, push or touch anything outside the file you are asked to write.
