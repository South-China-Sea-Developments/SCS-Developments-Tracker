# 18: Light tracker and a sharper banner

**What to build:** The tracker takes the same white theme as the rest of the site (the maintainer, 2026-10-27: "can the main page/tracker have the same white theme as the other pages?"), and the banner is served at twice its resolution so it spans the page at full sharpness until the institute supplies the original file.

**Blocked by:** 17

**Status:** done (2026-10-27).

- [x] The tracker is white: the sidebar on paper with ink text and hairline rules, the checks and controls in the site's light style, the events in view as rows on paper; the map on the light basemap (the vendored Positron style, as before ticket 17) with the sub-region polygons in light terms; the navigation band stays the logo's navy and the banner stays on the sea-coloured band. The dark basemap, its derivation script and its test go. *The tracker and map blocks of `style.css` restated in paper tokens (`--map-plane` is Positron's land colour, shown until the tiles arrive; `--map-zone` back to the teal; the canvas desaturated as before ticket 17); `build.py` inlines `positron-en.json`; `web/tools/`, `dark-en.json` and the vendor README's paragraph removed.*
- [x] The banner is a 2× Lanczos upscale of the file the maintainer sent (`web/static/img/banner.jpg`, 1420×608, with the sharpening it needs), shown at the wrap width at or below its own size, so it spans the page without browser scaling; the original from the institute replaces it as a drop-in when it arrives (same path, any size). *Pillow Lanczos 2× plus a light unsharp mask, JPEG quality 88 (133 KB); `.banner-img { width: min(100%, 1420px); max-height: 360px }` so the title and its rule stay in view at the wrap width.*
- [x] Every page renders without console errors at desktop, tablet and phone widths (seam 3); the public-face test asserts the sidebar and the map plane are light, the banner is the larger file, and the navigation band is still navy. *`test_public_face` updated; 263 tests pass.*
