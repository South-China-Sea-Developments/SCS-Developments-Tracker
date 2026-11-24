# 30 — The whole banner: folding on inner pages, a curtain on the home page

The maintainer chose options 1 and 4 of the banner mock-ups on 2026-11-22, with the logo visible in both.

- **Inner pages:** the whole banner (logo and title) on arrival, folding into the slim strip on the title's
  first line over the first scroll; the menu band stays against it; once folded the strip scrolls away
  with the page. Without the script, the strip as before.
- **Home page:** on a reader's first visit, the whole banner fills the screen on its sea colour for 1.6 s
  and lifts to reveal the map; a click, key, wheel or touch lifts it at once; it is remembered in the
  browser (localStorage) and never shown under reduced motion.
- The menu band keeps the logo on every page.

## Revised the same evening (maintainer)

- **Inner pages, option 2 instead of 1:** the slim strip on the title's first line opens to the whole
  banner, logo and all, under the pointer (or on keyboard focus), over the page; only the strip answers
  the pointer, so moving down onto the page closes it and nothing is blocked. On touch screens it stays
  the strip, a link home.
- **Curtain fills the screen:** the banner covers the screen wherever the logo and the whole title still
  fit across; otherwise it is scaled to just fit them, centred on its blue (thin bands at 16:10, none at 16:9).
- **Scroll zoom after a manual zoom:** the scroll's zoom is added to the reader's own view, which a zoom,
  pan or fit moves; it no longer stops once the reader has zoomed.

## Revised 2026-11-23 (maintainer)

- **Inner pages:** the strip no longer opens to the whole banner under the pointer or on keyboard focus; it
  stays the slim strip, a link home, everywhere. The curtain on the home page is unchanged.

## Replaced 2026-11-24 (maintainer): the masthead, option C

- **Every page, the home page included:** a thin masthead (64–92 px) replaces the strip: the institute's
  logo and "South China Sea Research Initiative" on the sea blue, the logo on the page's left edge, and the
  banner's reefs (its lower part, below the artwork's own title) filling the rest, fading in from the blue.
  The whole masthead is a link home.
- **The menu band:** no logo (it is in the masthead); the tracker's name and the links share one thin row
  from 1000 px; below that the links take their own row and scroll as before.
- The home page's opening curtain is unchanged.
