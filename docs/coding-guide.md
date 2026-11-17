# Coding guide: running the tracker the way Chubb built MATS

How to take this project from a source page to a published move without breaking the method it
continues. Every step says what to do, why Andrew Chubb did it that way, how it is done here, and the
mistake it guards against. Read Part I once; work Part II for every run; keep Part IV open while
deciding.

Sources, cited in brackets throughout: **[IS]** Chubb, "PRC Assertiveness in the South China Sea:
Measuring Continuity and Change, 1970–2015", *International Security* 45(3), 2021 (section names
from the accepted manuscript); **[App]** its methodological appendix (Harvard Dataverse,
doi:10.7910/DVN/3Y7NRU; text in `docs/codebook/chubb-2021-appendix.txt`); **[SR99]** Chubb,
*Dynamics of Assertiveness in the South China Sea: China, the Philippines, and Vietnam, 1970–2015*,
NBR Special Report 99, May 2022 (page numbers); **[MATS]** the dataset itself, MATS 1.02
(`data/raw/mats-1.02/`, with the MAVD columns in `data/raw/mavd-arcgis-2023/`); **[9DL]** Chubb,
"What the numbers can (and can't) tell us about the South China Sea dispute", 9DASHLINE, 2 Feb 2021;
**[Project]** this repository's ADRs, decisions and spec.

---

## Part I — The idea, and the one mistake that undoes everything

### 1. The tracker does not count assertive acts. It counts *changes* in assertive behaviour.

A MATS case — a **move** — is "an intensification of the PRC's assertiveness in comparison with the
previous year" [App, *Stage 2*]. The 132 PRC cases are "cases of year-on-year change" [IS, *Four types*],
not 132 incidents. Chubb says why: "the significance of state action in a contested maritime space often
depends heavily on the context, because states' observed behaviors today emerge from a background of
their own and others' past actions. Rather than approaching state behavior as a series of discrete
events, then, the framework … produces measurements of year-on-year changes in state behavior. Focusing
on changes in behavior — or moves — rather than events per se helps account for the context by
situating each observed state action within a stream of data points for its earlier actions" [SR99, p. 3].

So a Chinese coast guard ship blocking a Philippine resupply at Second Thomas Shoal in a year when it
did so every month of the year before is an **event** worth recording — it is evidence about the level
of behaviour — but it is **not a move**. It is covered by the earlier move's *Ongoing through*. If you
enter it as a new move, the series stops measuring escalation and starts measuring media coverage, which
is exactly the bias the method was designed to remove [IS, *PRC assertiveness by the numbers*; SR99, p. 3].

Every other rule in this guide follows from that one.

### 2. What "assertiveness" means here

"Statements and behaviors that strengthen the state's position in the dispute" [IS, *Assertiveness as a
variable*; SR99, p. 4]. A state's *position* has three components [IS]:

1. its **overall administrative presence** in the disputed area — not only land occupied, but "all state
   assets within the disputed area — from mobile units like vehicles, ships and aircraft, to fixed
   facilities like roads, buildings, airstrips, ports and sovereignty markers, as well as less visible
   manifestations of state presence such as cellular networks and scientific equipment";
2. its **ability to secure interests there using military force**;
3. its **ability to sustain the claim in international law** — hence the "sensitivity of states to
   potentially legally significant, but otherwise relatively innocuous, actions".

The test is observable: does the act strengthen the actor's position on one of these three? It can be applied "without
the need for strong subjective judgements about the state of mind of the actor" [IS]. Motive, provocation and
blame are not part of the test. "Merely maintaining a disputed claim involves some level of assertiveness"
[IS] — which is why *maintenance* is the baseline and only *change* is a case.

### 3. Four types, ordered, and a move takes the highest it meets

Declarative < Demonstrative < Coercive < Use of force, "based on their increasingly serious implications
for the positions of rival claimants" [IS, *Four types*]. The typology "categorizes state behaviors
according to the highest category for which they meet the criteria" [SR99, p. 5]: "patrolling a disputed
area is classified as a demonstrative behavior, though it may also involve declarative verbal
proclamations"; "direct interference with another state's construction project or resource survey will
belong unambiguously in the coercive category, even if it also entails declarative and demonstrative
activities"; seizure "will constitute a use of force, even though it usually also involves a buildup of
administrative presence (demonstrative), threats of punishment (coercive), and verbal claims (declarative)"
[IS; SR99, p. 6]. The four definitions, from the author:

- **Declarative** — "official claims over the disputed area that make no discernable threat to impose
  punishment on rival states": remarks by officials, domestic laws and regulations, diplomatic
  declarations, submissions to international authorities, changes in domestic administrative arrangements
  governing the area. They matter because they demonstrate non-recognition of rival claims and are
  "considered as evidence in international legal proceedings", and "typically stay in effect in perpetuity
  unless actively renounced" [IS].
- **Demonstrative** — "unilateral administrative behaviors — actions that manifest a state's presence or
  jurisdiction in the disputed area, but without directly confronting adversaries": air and sea patrols,
  scientific surveys, unilateral resource exploitation, construction, "state-sponsored civilian actions
  like tourism, activism and resource exploitation", and non-physical ones — "signing agreements with third
  parties over resource development, or domestic administrative or judicial proceedings over the disputed
  area" (Japan's prosecution of the trawler captain, 2010; nationalising the Senkakus, 2012). They
  "can constitute stepping stones to acquisition by fait accompli" [IS].
- **Coercive** — "the threat or use of punishment against an adversary": "physical interference with
  foreign activities in a disputed area, or the firing of warning shots", but also "formal and informal
  economic sanctions via the disruption of trade, through to threatening public statements, diplomacy and
  administrative moves" — Chubb's examples of *administrative* coercion are "promulgating territorial sea
  baselines that upgrade disputed waters to sovereign territorial seas under domestic law, or the
  establishment of Air Defense Identification Zones", because they "communicate threats to other state and
  non-state actors entering such areas" [IS]. The boundary with demonstrative: "Actions conveying a clear
  threat or warning to others … are not demonstrative but coercive" [IS, n. 24]. Coercion here includes
  deterrent as well as compellent threats, "to sidestep questions of whether the target had been engaging
  in encroachment or aggression" [IS, n. 27] — so a "defensive" warning is still coercive.
- **Use of force** — "the application of military violence or direct seizure of the disputed
  possession"; "the use of force does not necessarily involve military units, since civilian actors can be
  deployed to seize disputed possessions, as in the case of the PRC's occupation of Mischief Reef in 1994"
  [IS]. In the data, the 2012 Scarborough case (`CN201205`, "coercion against Philippine boats at
Scarborough Shoal, establishing constant presence") is coded force because China "seized Scarborough
Shoal" [SR99, p. 21] — control of the possession changed — whereas the 2013 "constant presence at Second
Thomas Shoal" (`CN201303`), where nothing changed hands, is demonstrative [MATS].

### 4. What is deliberately left out — and what is *not* left out

- **Cooperative and conciliatory acts** (joint patrols, resource agreements, consultations, CBMs) are not
  coded. Not because they do not matter, but because "actively conciliatory measures do not necessarily
  offset or mitigate assertive actions" [App, *Limitations*]; practically, "cooperation by definition
  requires two or more states … many unsuccessful attempts at pursuing cooperation are likely to go
  unobserved", and analytically "increased assertiveness will probably be weighted more heavily by rival
  claimants than conciliatory actions. Thus, implicitly equating the two by offsetting assertiveness
  against conciliatory actions in the same timeline could be misleading" [SR99, pp. 7–8]. The method
  *does* capture **moderation** — "shifts to fewer or less escalatory assertive actions" — through
  diminishment (§K). *In this project:* cooperative acts are out of scope by spec; a separate
  de-escalation tracker is the maintainer's own project and is not merged here.
- **Non-claimants** (US, Japan, Australia, India) are context, not coded actors [Project, spec]. Chubb
  coded a PRC statement aimed at the US as a PRC move with dyad U; the US act itself is never a case.
- **Reactions are not excluded.** The Philippines sending "three escort ships and two surveillance
  planes" after its survey ship was harassed at Reed Bank is a Philippine demonstrative move (`PH201101`)
  [MATS]; Vietnam's 2014 "unprecedented international public opinion campaign" against HYSY 981 is a
  Vietnamese declarative move (`VN201402`). The series records *behaviour*, whoever started it; the
  action–reaction reading is done afterwards, with the dyads [SR99, ch. 1]. Do not drop an act because
  the claimant was "only responding".
- **Significance is not weighted.** "The quantitative assertiveness framework implicitly gives equal
  weight to actions of varying significance" — the 2005 Tonkin shooting that killed nine Vietnamese and
  a 2011 increase in detentions each count once; the 2013–15 "massive land reclamation works … are also not weighted for
  their significance, except insofar as they enable further assertive actions in the future" [App, *Unit of
  analysis*]. Do not inflate an important year by splitting one intensification into several moves, and
  do not deflate a quiet one by merging distinct intensifications.

### 5. The two biases the method is built to resist

- **Present-centric bias.** "Alterations in PRC behavior are much more likely to have been observed in
  English-language sources in recent years than further back in the past" [IS]; the 1988 Johnson South
  Reef battle "was little more than a blip on the international media agenda" [SR99, p. 3]. The remedy
  is to mine the claimant's own historical sources — chronologies, yearbooks, agency reports — and to
  apply **stricter evidentiary standards to recent events**, "for it reduces the probability that
  changes detected will be spurious or overstated" [App, *Limitations*; SR99, p. 7]. The practical
  consequence for us: a 2025 candidate needs *more* to become a move than a 1985 one, not less.
- **Source-side bias.** Pro-PRC reference materials "overwhelmingly characterize China as the victim";
  but "if assertive PRC conduct is referred to in such sources, this is also a strong indication that it
  was intentional, rather than an accident or the result of unauthorized lower-level actions" [IS]. Read
  every source for what its author wanted to show, and weigh an admission against interest more than a
  claim in interest.

Two further caveats Chubb insists on: the data are "inevitably incomplete, for an assertive state and its
adversaries may both have incentives to keep such events secret" [App]; and "there may be a lag between
important political decisions that set in motion a policy change, and the observable manifestations"
[App; SR99, p. 8], so the series dates *behaviour*, never *decisions*, and must be "complemented by close
analysis of speech and text" before any causal claim [App, *Limitations*; 9DL].

---

## Part II — The workflow, A to Z

Each step: **Do** / **Why** / **Here** (where it lives in this repository) / **Don't**.

### A. Fix the baseline before coding year one

**Do.** For each claimant, write the list of known assertive actions before 1970 — occupations,
garrisons, patrols, laws, maps, protests — with a source for each.
**Why.** The series measures change "relative to 1970" [App, *Stage 2*]; without a baseline, 1970's first
patrol looks like a novelty when it may be the fifteenth year of one. Chubb's PRC list runs from the 1949
map through "1960–1973: average of 5 PLAN patrols per year in the Paracels" [App, *Baseline 1970*]. 1970
is the start because the ECAFE survey had just "sharply increased the incentives for claimants on all
sides to pursue those claims".
**Here.** `data/baselines/<claimant>.md`, one per claimant (ticket 11); the PRC's is Chubb's own, the
other five are the project's, each entry with a URL opened and a quote. They ship with every release.
**Don't.** Don't code a 1970s move for a claimant whose baseline you have not read. Don't backfill a
later decade before the earlier one without saying so (the year-on-year rule needs the previous year).

### B. Build the master timeline — cast the net wide (Stage 1)

**Do.** Collect *every* plausibly relevant dated development — the claimant's acts, rivals' acts, third
parties, statements, meetings, domestic politics, exogenous events — confirmed or not, each with its
source and the exact words that support it.
**Why.** Stage 1 is "the generation of a master timeline file … into which was entered any potentially
relevant historical developments … The aim in this process was to cast the net as widely as possible,
leaving analysis and verification to the second stage" [App, *Stage 1*]. Including unconfirmed items
"allow[s] time for evidence to emerge that could confirm or refute candidate cases" [App, *Limitations*].
The timeline is also the context you will need in step E to judge what the state would have done before.
**Here.** The events table *is* the master timeline [Project, CONTEXT "Master timeline"]. Three inlets
feed it: the weekly harvester (`pipeline/harvest`, the registered feeds in `pipeline/sources.json`), the
backfill compilers working from the archive list and `harvest/manual/BRIEF.md`, and the weekly run's
`Sidelines` table for things seen that are not events. Every candidate carries a verbatim excerpt the
importer re-fetches and checks; `pipeline.harvest archives` lists the historical sources per claimant.
The register of what no agent could compile is `docs/notes/backfill-gaps.md`.
**Don't.** Don't filter at collection time by "is this a move?" — that is Stage 2. Don't collect without a
date to at least the month and a source you opened. Don't let the inlet be English-language news alone:
Chubb's PRC series rests on the SOA *Dashiji*, the Spratly *Dashiji*, the NISCSS reports and the Ocean
and Fisheries yearbooks [IS, nn. 33–35]; for the other claimants, the equivalents are their own
ministries' releases, parliamentary records, gazettes and agency chronologies.

### C. Verify the candidate before you judge it

**Do.** Cross-check each candidate against a second source where one exists; ask who reported it and
why; set aside what cannot yet be confirmed rather than deleting it.
**Why.** "Each was cross-checked with other sources where available, and considered with specific regard
to possible motivations that could bias the source of the information. Several candidate cases from the
main timeline were set aside pending possible future confirmation" [App, *Verification*]. Those set-aside
cases survive in the data as `Other_Possible_Cases` on the MAVD table [MATS] — the method keeps its
doubts on the record.
**Here.** The importer flags unverified excerpts and possible duplicates; the review page shows the
sources side by side. A candidate that is real but unconfirmed is *rejected with a note* saying so, or
left as a candidate; the gaps register holds what could not be compiled at all, marked ◆ (add by hand?),
▲ (in the set, confirm) or ○ (excluded by rule).
**Don't.** Don't accept a single-source claim by a rival government as fact (Vietnam's account of what the
PLAN did is evidence of a *Vietnamese* protest and a *possible* Chinese act). Don't treat a satellite-image
date as the act's date without saying the precision is the imagery's.

### D. Is it an assertive act of this claimant at all?

**Do.** Ask four questions. (1) Is the actor the claimant *state* — government, forces, agencies, state
companies, or state-sanctioned civilians (Chubb counts "state-sponsored civilian actions like tourism,
activism and resource exploitation" [IS])? (2) Does the act strengthen the actor's position on
administrative presence, military ability or legal viability (§I.2)? (3) Is it non-cooperative? (4) Does
it concern the South China Sea claim (not the Taiwan Strait, not the East China Sea, not the Bashi
Channel, not the Sulu or Arafura Seas)?
**Why.** The definition is the filter [IS, *Assertiveness as a variable*]; the exclusions are deliberate
(§I.4).
**Here.** The brief's "What counts as an event" paragraph is this test in compiler form. The sub-region
field (ten polygons, `data/reference/mavd_subregions.geojson`) is the geographic test; the Natuna waters
and Pratas lie outside the ten polygons but inside the dispute, so an event there carries no sub-region
and still counts.
**Don't.** Don't code a private company, a fishing cooperative or a professional association as the
state unless the state sanctioned the act. Don't code a non-claimant's act (a US transit, an Australian
flight) — but do code the claimant's *statement* about it if the statement asserts the claim (China's
"intruded into Chinese territorial waters" over USS Benfold at the Paracels is a PRC declarative act,
dyads `CU` and `CV` since the Paracels are Vietnam's claim too; the transit is not an event). Don't code a mere "we urge restraint" or "all parties should
comply with international law" — it asserts nothing.

### E. The intensification test — the heart of the method

**Do.** Put the event beside *everything the same claimant did in the previous calendar year*. It is a
move only if it is one of three things: **(a) novelty** — "a new method of advancing the claim, unseen in
previous time periods"; **(b) frequency** — "more frequent than in previous time periods, for example an
increase in patrol activity or resource exploration and exploitation"; **(c) scope** — "applied over a
broader geographic area than in previous time periods" [IS; SR99, p. 6]. Name which one.
**Why.** This is what makes the count a measure of escalation rather than of activity (§I.1). The
previous *calendar year* is the reference because it "served this project's requirement for fairly precise
indications of the timing of policy change" [App, *Stage 2*] and "seems a less arbitrary choice than wider
units of time" [App, *Unit of analysis*].
**The counterfactual.** Chubb's own worked case: "PRC on-water enforcement actions against foreign fishing
increased in 2007, but this could not automatically be considered a case of intensified assertiveness.
The number of Vietnamese fishers operating in the Paracel Islands had increased sharply, and if this had
occurred in previous years it is quite likely that PRC enforcement would also have quantitatively
increased. The case's eventual inclusion in the dataset was on the qualitative basis that China's
enforcement methods shifted from the previous practice of harassment and warnings, towards confiscation
of property and detention of Vietnamese personnel" [App, *Verification*]. So: more of the same because
there was more to react to is not a frequency move; a *change of method* is a novelty move. Ask, in Chubb's words, "how
the state would have responded if the same circumstances had arisen in the past".
**Know the artefact.** The year-on-year unit has a known consequence: PRC survey activity "observed in
similar geographical areas in 2010 and 2007" and again in 2014 is "three separate cases of
intensification of assertive activity, followed by its diminishment the following year", where a longer
unit would see one [App, *Unit of analysis*]. That is the rule, not a bug; apply it consistently, and let
*Ongoing through* and diminishment carry the rest. Its corollary cuts both ways: a method last seen years
ago but absent in the previous year is *new again* when it reappears.
**Here.** The review page and the Airtable Candidate Detail show the claimant's previous-year moves and
same-year moves beside every candidate (`previous_year_moves`, `same_year_moves`); forming a new move
requires `intensification_criterion` ∈ {novelty, frequency, scope} and the validator refuses a
project-coded move without one. The 2016–2020 sets were compiled so that 2016 is judged against Chubb's
2015 moves; each backfill decade is judged against the one before.
**Don't.** Don't form a move because an incident was dramatic, widely reported, or condemned. Don't form a
move because it is the first such act *you have seen* — check the previous year and the baseline. Don't
call a frequency increase a move without a number or a stated comparison ("fifth such patrol of the year"
against "two in all of last year"). Don't code a continuation as a move: it belongs to the earlier move's
*Ongoing through*.

### F. Group events into the move

**Do.** One move per intensification. A move may be a single action or a closely linked series of actions
[Project, CONTEXT — the project's gloss; Chubb's cases run from one dated act to a year-long pattern]. Several distinct intensifications in one year are several moves
(China 2012: Scarborough seizure, economic sanctions on Philippine fruit, Sansha City — separate moves
[SR99, p. 21]); one intensification shown by many incidents is one move with many events (China 2007:
"Regular rights protection patrols begin, and then expand in scope" — one move, `CN200701`, carrying every
patrol [MATS]).
**Why.** The count is of changes in behaviour; splitting one change across incidents inflates the year
(§I.4, equal weight). Linking events to a move is what lets the series keep the detail Chubb had to
summarise [Project, ADR 0002].
**Here.** Decide *merge* (into an existing move of the same claimant and year, or into a move formed from
another candidate in the same batch via `move_of_event`), *new move*, *duplicate* (another report of an
accepted event — status `merged`), or *reject*. Merge checks claimant and year.
**Don't.** Don't merge a 2024 event into a 2023 move: a move is a year's intensification, and the
validator binds an event to a move of its own claimant and year. If the behaviour continued into 2024 at
the same level, the 2024 event is decided *reject* with the note "continuation of <move_id>", and the 2023
move's *Ongoing through* is moved to 2024 by a separate edit to `moves.csv` (§K). That the continuation
evidence then leaves the map is a known
limitation of the current schema; a `continuation` status attached to the earlier move would be an
additive change (ADR 0001) and is the natural next ticket once the first real reviews show how often it
arises. Don't form two moves for the same intensification because two agencies were involved.

### G. Code the Type

**Do.** Assign the highest type the move's acts meet (§I.3). Write the reason in one sentence.
**Why.** The ordinal rule [SR99, p. 5]. Ambiguity is expected: two independent re-coders of Chubb's 132
narratives matched him on 92.4% and 87.1% of cases [App, *Coding checks*] — a coder who never hesitates is
not reading closely.
**The hard boundaries.**
- *Demonstrative vs coercive*: a patrol is demonstrative; a patrol "conveying a clear threat or warning
  to others" (radio warnings to leave, shadowing with intent, blocking) is coercive [IS, n. 24]. A law is
  declarative; baselines "that upgrade disputed waters to sovereign territorial seas" or an ADIZ are coercive
  [IS]. A fishing ban *announced* is declarative; *enforced* against foreign boats it is coercive.
- *Coercive vs force*: physical interference, seizure of boats, detention of crews, water cannon, ramming
  are coercive; a change in control of a *feature*, or military violence, is force. Scarborough 2012 is
  force because the shoal was seized (`CN201205`); the Philippines' 1970 occupation of Nanshan is force
  (`PH197001`); "constant presence" at Second Thomas in 2013 without a change of control is demonstrative
  (`CN201303`) [MATS].
- *Declarative vs demonstrative*: a statement is declarative, and so is an administrative act with no
  presence attached — "changes in domestic administrative arrangements governing the disputed area" [IS];
  Chubb coded the 1983 naming of 287 features declarative (`CN198302`) [MATS]. An administrative act that
  *manifests* jurisdiction on the ground — a court case over the area, a post office, household
  registration, a weather station, resettlement — is demonstrative (`VN200901`) [IS; MATS].
**Here.** `suggested_type` from the compiler is a suggestion; the coder's type is the move's. The
agreement report compares the two.
**Don't.** Don't type by actor ("coast guard ⇒ coercive", "ministry ⇒ declarative"). Don't type by
severity of outcome (a fatal collision is still coercive if the possession did not change hands). Don't
let the *target's* reaction set the type.

### H. Domains and issues

**Do.** Tick every domain and issue that applies; both are non-exclusive [SR99, p. 20].
**Why.** "Domain" is the political theatre: *domestic* — "laws, directives, administrative changes, and
propaganda aimed at the home population"; *diplomatic* — "statements and behaviors directed toward
international audiences or in cooperation with foreign actors, but which take place outside the physical
disputed area"; *physical* — "real-world actions undertaken in the geography that is subject to the
dispute" [SR99, p. 20]. "By definition, declarative actions can occur in the domestic or diplomatic
domain. Actions that occur in the physical domain are, at a minimum, demonstrative" [SR99, n. 24] — a
consistency check on your type. Issues: *military* — "obtaining an advantage in the event of armed
conflict (or denying the same to an adversary)"; *administrative* — "the state's civilian administrative
capacities over the area"; *energy*, *fisheries*; *politics* — "the views and actions of domestic and
international audiences toward the dispute" [SR99, p. 20].
**Here.** 0/1 flags on the move; the packed MATS codes are derived.
**Don't.** Don't tick *physical* for a statement made in a capital about the sea. Don't tick *military*
for a coast-guard patrol unless it bears on a military advantage. Don't leave a move with no issue.

### I. Dyads — who the move bears on

**Do.** Write actor first, then every state whose claim the act impinges on. The rules Chubb used
[App, *Dyadic and issue analysis*]: a feature-specific act implicates the claimants to that feature
(Paracels → V; Scarborough → P); an act in the Spratly outposts → P and V, "except where they had clear
strategic implications for other states, such as the large-scale island-building campaign"; a claim to
the Spratlys as a whole → M, P, V; an act over the whole nine-dash-line area → add B for energy and I for
fisheries; "implications for states at large — such as introduction of civil airspace regulations, or
military exercises taking place in unspecified waters" → A; and U, which the appendix uses for the PRC–US
dyad ("disputes over surveillance activities and interpretations of international law between the PRC
and the US") while the dataset's own legend reads "U = Unclear" [MATS, Information sheet] — in practice
Chubb's U cases are the US-related ones. Taiwan is R, and Chubb used it where an act touched the ROC's
holdings or claim concretely (`PR` 45 times, `VR` 34) but added it to a Chinese Spratly-wide statement
only once (`CN198801`).
**Why.** Dyads are how the action–reaction dynamics are read later ("each advance impinging on the
interests of a broadening array of states" [SR99, ch. 1]); they are not a judgement of blame.
**Here.** `dyads`, space-separated, actor first (`CV`, `PC`); for the three new claimants the actor codes
are M, I, R. Follow Chubb's practice for R: a Taiwanese act regarding Itu Aba implicates C, P and V; a
Chinese, Vietnamese or Philippine act implicates R when it concretely touches Taiping, the Pratas or the
ROC's claim, not automatically for every Spratly-wide statement — adding R across Chubb's own rows would
be a re-coding, which ADR 0001 forbids.
**Don't.** Don't write the target first. Don't code only the state named in the headline when the act
touches several claims. Don't use U for "no particular target" — that is A; reserve U for the US (and, if
you must, the unclear), and say which in the note.

### J. Sub-regions

**Do.** Tick each of the ten sub-regions the move's acts fall in; a declarative move about the claim in
general may have none.
**Why.** "Pinning assertive state activities to specific geographic coordinates is a challenge … many
real-world assertive behaviors … take place over an expanse of sea rather than at a single point. In
addition, many assertive behaviors in the declarative type pertain to the state's claims in general"
[SR99, p. 31]. The ten zones are defined by "environment, resources, the presence of disputed islands,
and state claims".
**Here.** Sub-region at move level is a coding; at event level, placement is a *lookup* — coordinates
over a feature name over an extractor's guess (gazetteer, spec amendment ticket 08) — and the validator
checks that a stated sub-region is the one the coordinates fall in.
**Don't.** Don't invent coordinates. Don't put the Natuna waters or Pratas in a polygon they are not in.

### K. Duration: ongoing, intensified further, or diminished

**Do.** For every move, estimate the last year the behaviour continued (*Ongoing through*). Each later
year, re-ask for every open move: did it continue, intensify further (a new move) or diminish? Record
diminishment in words.
**Why.** "Once a given action is identified as a case of assertive behavioral change, it is important to
consider whether, in subsequent time periods, it intensified further, continued or diminished" [IS]. The
default: "an absence of evidence of equivalent actions in the following year was treated as a
diminishment of that particular aspect" — with the caution for sparse data: PRC fishing rose in 1994 and
again in 2001 with nothing known in between, so "the assumption was made that Chinese fishing had been occurring at approximately the
same level across that time period – a more cautious conclusion than to assume either further increases
or diminishment. PRC fishing was therefore regarded as having intensified in 1994, and continued over the
following seven years, before intensifying again in 2001" [App, *Verification*]. Chubb's own diminished
notes are terse and specific: "No known detentions of VN personnel in Paracels" (1980); "Fewer People's
Daily island sovereignty assertions" (1993) [MATS, MAVD column]. This is the only way the series records
moderation (§I.4).
**Here.** `ongoing_through`, `ongoing_through_notes`, `diminished_notes` on the move. A continuation
candidate is rejected with a note naming the move it continues. `queue decide` writes only event fields
and new moves; extending a move's `ongoing_through` or adding a diminished note is an edit to
`data/moves.csv` in its own pull request, checked by the validator — and for a `coded_by = chubb` row it
needs a documented line in `data/corrections.csv`, because every MATS field of those rows is guarded.
Chubb's MAVD diminished column also records a few *conciliatory* acts for the Philippines and Vietnam
(1988, 1996); here those stay out of the moves and go in `diminished_notes` only where they mark the end
of an assertive practice.
**Don't.** Don't leave `ongoing_through` at the move's year for a law, a structure or an administrative
arrangement that is plainly still in force — those "remain in place until abolished or abandoned" [IS,
*Layers*]. Don't infer diminishment across a decade of missing sources; say the level is unknown.

### L. Write the description

**Do.** One paragraph per move, in Chubb's form: date (to the month where known), who did what, to whom,
where, then the sources inline in parentheses, and a sentence on how it relates to the previous year
where that is not obvious.
**Why.** The description is the evidence the coding rests on and what a re-coder is given [App, *Coding
checks*]. Chubb's: "2007: At least two CMS 'special operations' against 'foreign countries'
rights-infringing activities', including June–July drilling incident in Paracels, which involved ramming
(SOA, ZGHYNJ 2008, 127; CCTV, Lan Jiang Weishi). This was preceded by CMS exercises in May/June 2007
[that] were 'the largest air-sea patrol exercise since the founding of CMS' in 1998" [MATS, `CN200702`].
**Here.** `description` on the move; the events underneath carry dates, places, excerpts and URLs, so the
description can be shorter than Chubb's had to be, but it must still name the intensification.
**Don't.** Don't paraphrase a quotation as if it were one. Don't write the description from the headline;
write it from the sources.

### M. Decide, validate, merge — and let nothing be accepted by a machine

**Do.** Decide every candidate yourself on the review page or in Airtable; export; apply with
`pipeline.queue decide`; let the validator run; merge the pull request.
**Why.** "machines harvest and propose, humans decide" [Project, ADR 0003]; decision 07: no project-coded entry enters
the dataset until the maintainer has reviewed it himself. The validator is the merge gate — schema,
integrity, and the comparability rule that the 1970–2015 counts for CN, VN and PH equal MATS 1.02
exactly [Project, spec]. That rule counts *every* accepted move of those claimants in those years, so no
project-coded move may be added to China, Vietnam or the Philippines before 2016: a gap found in a
MATS-era year goes to the author as a proposed correction, and backfilled events for those years attach to
Chubb's existing moves. A move formed by `decide` is `accepted` at once; merging the pull request is the
acceptance; `pending` exists only for `VN197304`, awaiting the author.
**Here.** The review PR is the queue; the decisions file is the same whichever front end produced it;
with Airtable, archive first (`pipeline.airtable archive`, ADR 0005), then apply, then clear.
**Don't.** Don't edit `coded_by = chubb` rows except by a documented correction. Don't bypass the PR.

### N. Publish and version

**Do.** Tag a release; publish accepted moves only; label project coding as such everywhere it appears;
cite Chubb on every page.
**Why.** A citation must name a fixed version [Project, ADR 0004]; comparability with the published
analyses is the project's licence to exist [Project, ADR 0001]; the author asked to check that 1970–2015
match his [Project, spec, user story 16].
**Here.** `pipeline.release`, `CITATION.cff`, the Downloads page; the site says nothing about the
project's own progress [Project, decision 06 as amended].
**Don't.** Don't publish pending moves. Don't restate MATS totals without the comparability test green.

### O. At the end of each claimant-year, read the year as a whole

**Do.** Before closing a claimant-year, list its moves together and ask: do they describe distinct
intensifications? Is anything a continuation in disguise? Does the count fit what the method expects?
**Why.** Chubb's reference rates for the PRC, from the 132-case series analysed in the article: about
1.8 moves a year outside the surges, 3.0–5.1 inside them, 2012 the peak at nine [IS, *Increasing
assertiveness as a constant*, *Breakpoint 2007*; App, Table A2]. MATS 1.02, the version the validator
enforces, has 144 PRC cases (111 Vietnam, 102 Philippines), ten in 2012, about 2.0 a year outside the
surges and 5.7 for 2007–15. For 2016 onward he expected "five to seven likely cases of new assertive activity … each year since 2015, with
two to three of these cases falling within the coercive category" [SR99, p. 39]. A claimant-year with 25
moves has almost certainly counted events; a year with none for China since 1990 would be the first.
Vietnam and the Philippines run lower, and Malaysia, Indonesia and Taiwan lower still.
**Here.** The Trends page and `validator` aggregates give the counts; the gaps register says what could
not be found, so a quiet year can be told from an unsearched one.
**Don't.** Don't adjust a count to hit the expected rate — use the rate as a prompt to re-read, not as a
target.

### P. Check yourself the way Chubb did

**Do.** Keep the machine's suggestions beside your decisions; periodically have a second person re-code a
sample of moves from the narratives alone; log disagreements and what they taught about the rules.
**Why.** Chubb's two re-coders — one who knew the dispute, one who did not — reached 92% and 87% type
agreement, and both found an even sharper post-2007 rise in coercion, which "should increase confidence
that the qualitative behavioral change identified in 2007 is the result of a qualitative shift in the
PRC's conduct, rather than biases of the author" [App, *Coding checks*]. The check is what lets a
continuation be trusted as a continuation.
**Here.** The agreement report (`data/agreement.json`, Methodology page) measures suggestion against
decision per extractor and per year; the gaps register and the review archive (`harvest/airtable/`) keep
the record of what was seen and typed.
**Don't.** Don't treat high machine–coder agreement as validation of the coder; it validates the
suggestions. Don't change a rule to fit a hard case without recording the rule change (ADR).

---

## Part III — Worked cases from this tracker's own candidates

1. **An event that is not a move.** *Indonesia 2023: KKP seizes Vietnamese fishing boats in the North
   Natuna Sea (several reports).* Indonesia has seized Vietnamese boats in Natuna waters every year for two
   decades. More seizures than in 2022 is not yet a frequency move: apply the counterfactual (§E) — if more
   Vietnamese boats came, more seizures is what Jakarta would have done in any earlier year. It becomes a
   move if the *method* changed (sinking at sea where boats were previously escorted to port; firing where
   there had been boarding), the *area* widened, or the rate rose with the same inflow. Otherwise record
   the events, reject them as continuation naming the standing move, and extend that move's
   `ongoing_through` in `moves.csv`.

2. **A reaction that is a move — judged against last year, not against history.** *Philippines, Feb
   2023: the Coast Guard begins publishing imagery and accounts of Chinese actions (the "transparency
   initiative").* It answers Chinese acts; that does not disqualify it. Nor does the fact that Manila
   publicised Chinese acts in 1995 (`PH199501`, whose description notes publicity "has been a regular
   practice of the Philippines … since") — the comparison is with 2022, and a method absent in 2022 is new
   again in 2023 [App, *Unit of analysis*]. So the question is whether the systematic, near-daily release
   of imagery is a new method or a sharp rise in frequency compared with 2022's occasional statements. If
   yes → new move, declarative, domains diplomatic + domestic, issue politics, dyad PC, with the criterion
   named.

3. **The counterfactual.** *China 2024: more Second Thomas resupply missions blocked than in 2023.* The
   Philippines also ran more missions. Ask what China would have done in 2023 with the same number of
   missions. The 17 June 2024 boarding with bladed weapons is a change of method — novelty — and coercive
   (physical interference and punishment by a coast guard; no feature changed hands and no military
   violence was applied, so not force, whatever the injuries — §G, "don't type by severity"); the extra
   water-cannon episodes alone are not a frequency move if the rate per mission is unchanged.

4. **The coercive/demonstrative line.** *Taiwan, Jul 2012: the coast guard moves 40 mm guns and mortars
   to Taiping; Sep 2012: a live-fire drill with legislators present.* Arming an outpost and drilling on
   it manifest presence and military ability without threatening a named party → demonstrative (issue
   military). Had Taipei announced the guns would fire on vessels entering the restricted waters, the
   "clear threat or warning" test would make it coercive.

5. **The declarative threshold.** *Vietnam, Jul 2022: the spokesperson "reaffirms sovereignty" over the
   Paracels after a Chinese drill.* Vietnam says this every year. A declarative move needs *more*
   statements, a *new* kind (a note verbale to the UN where there were only press lines; a law), or a
   *wider* claim. For the PRC Chubb used a proxy — People's Daily articles up by a third on the previous
   year, to a minimum of five [App, Figure A1]; no equivalent is defined for the other claimants, so a
   frequency move on statements needs the two counts written down, and a standing proxy for Vietnam or the
   Philippines would be a project decision to record. One more reaffirmation is continuation.

6. **Force, not coercion.** *China, Apr 2025: coast guard officers land on Sandy Cay and raise the
   flag; the Philippines denies a seizure and lands its own party days later.* If presence was not
   established, this is demonstrative (a landing) or coercive (if it blocked others); it becomes force only
   where control of the feature changed, as at Scarborough in 2012. The Philippine counter-landing is a
   Philippine demonstrative move if landing on Sandy Cay was new for Manila compared with 2024 — a landing
   years earlier does not make it old.

---

## Part IV — The checklist before you form a new move

1. Is the actor the claimant state (or state-sanctioned)? Is the act non-cooperative, in the South China
   Sea, about the claim?
2. Have I read the claimant's **previous calendar year** — all its moves, their `ongoing_through` — and
   the baseline if this is the first decade? (Earlier years do not count against novelty; last year does.)
3. Which of **novelty / frequency / scope** applies, in one sentence? If frequency, what are the two
   numbers?
4. Would the state have acted the same way last year in the same circumstances? If yes, it is not a move
   unless the *method* changed.
5. Is this the same intensification as another candidate this year? Then merge, don't multiply.
6. Type: the **highest** category met — is there a discernible threat or punishment (coercive)? Did
   control of a possession change or was violence used (force)?
7. Domains and issues ticked; physical ⇒ at least demonstrative; a statement is never physical.
8. Dyads actor-first, every claim impinged on; A for states in general, U for the US.
9. Sub-regions where the acts happened; none is allowed for a general declarative.
10. `ongoing_through` set with the duration rule; last year's open moves re-checked for continuation or
    diminishment.
11. Description written from the sources, with the intensification named and the sources inline.
12. Does the claimant-year count look like a count of changes, not of headlines?

If an answer is "I don't know", the candidate stays a candidate, and the gap goes in the register.

---

## Appendix — where each rule comes from

| Rule | Source |
|---|---|
| Assertiveness = statements and behaviours that strengthen the position; three components | IS, *Assertiveness as a variable*; SR99 pp. 4–5 |
| Four ordinal types; highest category met | IS, *Four types*, Table 1; SR99 pp. 5–6 |
| Coercive includes deterrent threats; "clear threat or warning" boundary | IS nn. 24, 27 |
| Force includes civilian seizure | IS, *Use of force* |
| Move = year-on-year intensification; novelty, frequency, scope | IS, after Table 1; App, *Stage 2*; SR99 p. 6 |
| Previous calendar year as reference; its artefacts | App, *Unit of analysis* |
| The counterfactual test (2007 fisheries) | App, *Verification* |
| Two-stage collection: master timeline, then refined series | App, *Stage 1–2*; SR99 p. 7 |
| Historical sources against present-centric bias; stricter standards for recent events | IS, *By the numbers*; App, *Limitations*; SR99 pp. 3, 7 |
| Cooperation excluded; moderation captured as diminishment | App, *Limitations*; SR99 pp. 7–8 |
| Equal weight; no significance weighting | App, *Unit of analysis* |
| Duration default and the sparse-data caution | App, *Verification*; IS, *Layers* |
| Domain and issue definitions | SR99 p. 20 and n. 24 |
| Dyad rules | App, *Dyadic and issue analysis* |
| Ten sub-regions | SR99 ch. 3 |
| Baseline 1970 and the PRC list | App, *Baseline 1970* |
| Re-coding check, 92%/87% | App, *Coding checks* |
| Expected rates (1.8; 3–5; 5–7 post-2015) | IS; App Table A2; SR99 p. 39 |
| Reactions count; dyads carry the dynamics | MATS `PH201101`, `VN201402`; SR99 ch. 1 |
| Machines harvest and propose, humans decide; files canonical; additive scheme | Project ADR 0001–0004, decision 07 |
