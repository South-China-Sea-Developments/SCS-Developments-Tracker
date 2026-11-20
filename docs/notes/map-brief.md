# Brief: a map that shows how assertiveness evolves (for the week of 2026-11-23)

The maintainer, 2026-11-20: the current map is a series of numbers that grows, which does not grab
attention; the NBR map's coloured spots are not engaging either. Anyone should understand **at a glance
that the conflict is evolving in certain ways in certain parts of the sea** — without the other extreme,
"a mess of colours pouring onto a maritime map". Expect a spec, a mock to approve, then several rounds of
tweaking.

Starting principles (to argue with, not settled):

- **One colour ramp, not many.** Each of the ten sub-regions is filled by one measure of assertiveness in
  the period — moves weighted by type (declarative < demonstrative < coercive < force) — on a single
  sequential ramp. The footprint grows in depth, not in variety.
- **Claimant is a choice, not a colour.** All claimants by default; a selector narrows to one. Six
  claimant hues on one sea is where the mess comes from.
- **Change over time as small multiples first.** Five or six period maps side by side (1970s … 2020s) show
  the shift (Paracels → Spratlys → southern shoals) without pressing play; an animated, scrubbed sequence
  for those who want it.
- **Events are detail on demand.** Dots and counts appear on zoom or on clicking a sub-region, to explain
  the colour, not to compete with it.

Open questions for the spec: the weighting of types; whether to normalise by period length; how to show
the comparability break (CN/VN/PH Chubb-coded to 2015, project-coded after; MY/ID/TW project-coded
throughout); whether a companion per-claimant timeline coloured by the highest type reached belongs on the
same page; accessibility of the ramp in light and dark.

Order of work: maintainer says in a few lines what someone should *see* in 30 seconds → one-page spec with
a mock → build → tweak. Opus for the design, Sonnet for the build.
