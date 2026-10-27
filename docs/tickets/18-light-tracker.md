# 18: Light tracker and a sharper banner

**What to build:** The tracker takes the same white theme as the rest of the site (the maintainer, 2026-10-27: "can the main page/tracker have the same white theme as the other pages?"), and the banner is the institute's own high-resolution artwork (2219×950), which the maintainer supplied the same morning.

**Blocked by:** 17

**Status:** done (2026-10-27).

- [x] The tracker is white: the sidebar on paper with ink text and hairline rules, the checks and controls in the site's light style, the events in view as rows on paper; the map on the light basemap (the vendored Positron style, as before ticket 17) with the sub-region polygons in light terms; the navigation band stays the logo's navy and the banner stays on the sea-coloured band. The dark basemap, its derivation script and its test go. *The tracker and map blocks of `style.css` restated in paper tokens (`--map-plane` is Positron's land colour, shown until the tiles arrive; `--map-zone` back to the teal; the canvas desaturated as before ticket 17); `build.py` inlines `positron-en.json`; `web/tools/`, `dark-en.json` and the vendor README's paragraph removed.*
- [x] The banner is the institute's high-resolution artwork (`web/static/img/banner.jpg`, 2219×950, JPEG quality 88, 271 KB), shown at the wrap width, cropped from the top on wide screens so the logo, the title and its rule stay in view. *The first build of this ticket used a 2× Lanczos upscale of the 710px file; the maintainer sent the original before merge and it replaced it at the same path. `.banner-img { width: 100%; max-height: 360px }`.*
- [x] Every page renders without console errors at desktop, tablet and phone widths (seam 3); the public-face test asserts the sidebar and the map plane are light, the banner is the larger file, and the navigation band is still navy. *`test_public_face` updated; 263 tests pass.*
