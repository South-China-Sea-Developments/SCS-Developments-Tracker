# Public site

A self-contained static bundle built from `data/*.csv` by `python -m web.build`. No framework, no build chain: Jinja2 templates, one stylesheet, one script, one vendored font (Instrument Sans, OFL). Relative paths only, so the output folder can be dropped onto any host (GitHub Pages for now; ASPI later) or opened from disk.

## Design notes

Subject: a research dataset about contested waters. Audience: researchers, analysts, journalists. Job: trends at a glance, then down to the evidence.

- **Identity device:** the masthead carries a faint graticule, a nod to hydrographic charts. It is the only decoration; everything else is data and type.
- **Type:** Instrument Sans throughout, one family; headline weight 600 with tight tracking; no all-caps labels, no eyebrows.
- **Colour:** page plane is a pale hydrographic tint, surfaces near-white, ink blue-black. Claimants use the dataviz categorical palette in fixed slot order (China, Vietnam, Philippines, Malaysia, Indonesia, Taiwan) so a filter never repaints survivors. Move types are an ordered intensity scale and use one blue ramp, pale (declarative) to dark (use of force). Both palettes validated with the dataviz validator in light and dark mode.
- **Marks:** stacked columns ≤ 24px wide, 4px rounded data-end, surface-coloured gaps between segments (2px, 1px when bands are narrow), hairline solid gridlines, muted axis ticks, tabular figures on ticks and in tables.
- **Interaction:** one hover tooltip per column (values lead, labels follow, line keys), keyboard focus shows the same; one filter row above everything it scopes; every chart has a table-view twin (the WCAG-clean equivalent, and the relief for the two light-mode hues under 3:1 contrast).
- **Responsive:** a year band never drops below 8px; the chart scrolls instead of squashing. Small multiples go to one column below 440px.

Tried and rejected: three-column small multiples on desktop (bands too thin to read); hover targets only on years with data (a year with none should still answer).
