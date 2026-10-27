"""Derive the tracker's dark basemap style from the vendored Positron style.

The tracker (ticket 17) draws the event map on a dark basemap in the manner of CFR's Global
Conflict Tracker: slate land on a navy sea, light labels with dark halos, boundaries as pale
dashed lines, roads and buildings nearly invisible at the zooms the map uses. Rather than vendor
a second upstream style, this script recolours ``positron-en.json`` layer by layer (the English
label expressions, sprite and glyph URLs stay as they are; the unused shaded-relief raster *source*
is dropped — Positron declares it but draws no layer from it) and writes ``dark-en.json`` next to
it. It is deterministic: running it twice gives the same bytes. Run it after refreshing the Positron file:

    python -m web.tools.derive_dark_style

The colours are the site's tokens stated as literals: the style is JSON, so it cannot read CSS.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE.parent / "static" / "vendor" / "openfreemap"

SEA = "#0a1a30"            # the sea, a shade under the site's --sea so the sub-region polygons read on it
LAND = "#2a3b4d"           # slate land
LAND_2 = "#2f4154"         # parks, woods, residential: one step lighter so texture survives faintly
WATERWAY = "#163052"
ROAD = "#36485b"
ROAD_CASING = "#2a3b4d"
BOUNDARY = "#8fa3b5"
LABEL = "#d6dee6"
LABEL_MUTED = "#9fb0bf"
WATER_LABEL = "#7fa6c8"
HALO = "rgba(10, 26, 48, 0.85)"

FILLS = {
    "park": LAND_2, "water": SEA, "landcover_ice_shelf": LAND, "landcover_glacier": LAND,
    "landuse_residential": LAND_2, "landcover_wood": LAND_2, "building": ROAD_CASING, "aeroway-area": LAND,
    "road_area_pier": LAND,
}


def recolour(layer: dict) -> dict | None:
    """The same layer with dark paint; None drops it."""
    lid, ltype = layer["id"], layer["type"]
    paint = dict(layer.get("paint", {}))
    if ltype == "raster":            # none in Positron today; a raster layer would be a light image the dark map does without
        return None
    if ltype == "background":        # the background is the land; water is drawn over it
        paint["background-color"] = LAND
    if ltype == "fill":
        paint["fill-color"] = FILLS.get(lid, LAND)
        paint.pop("fill-outline-color", None)
        if lid == "landcover_wood":
            paint["fill-opacity"] = 0.6
    elif ltype == "line":
        if lid.startswith("boundary"):
            paint["line-color"] = BOUNDARY
            paint["line-opacity"] = 0.7
            paint["line-dasharray"] = [3, 2] if "disputed" in lid else [6, 3]
        elif lid.startswith("waterway") or lid == "road_pier":
            paint["line-color"] = WATERWAY if lid.startswith("waterway") else LAND
        elif "casing" in lid:
            paint["line-color"] = ROAD_CASING
        else:
            paint["line-color"] = ROAD
            paint["line-opacity"] = 0.8
    elif ltype == "symbol":
        if lid.startswith("water"):
            paint["text-color"] = WATER_LABEL
        elif lid.startswith("label_country") or lid in ("label_city_capital", "label_city", "label_state"):
            paint["text-color"] = LABEL
        else:
            paint["text-color"] = LABEL_MUTED
        paint["text-halo-color"] = HALO
        paint["text-halo-width"] = 1.2
        paint["text-halo-blur"] = 0.5
    out = dict(layer)
    out["paint"] = paint
    return out


def derive(src: Path = VENDOR / "positron-en.json", dst: Path = VENDOR / "dark-en.json") -> dict:
    style = json.loads(src.read_text(encoding="utf-8"))
    layers = [l for l in (recolour(layer) for layer in style["layers"]) if l]
    style["sources"] = {k: v for k, v in style["sources"].items() if v.get("type") != "raster"}
    style["layers"] = layers
    style["name"] = "OpenFreeMap Positron recoloured dark, English labels (SCS Developments Tracker)"
    style["metadata"] = {"source": style.get("metadata", {}).get("source", ""),
                         "derived": "web/tools/derive_dark_style.py recolours every layer of positron-en.json and drops the unused shaded-relief raster source; the English label expressions, the vector source, sprite and glyphs are unchanged"}
    dst.write_text(json.dumps(style, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return style


if __name__ == "__main__":
    s = derive()
    print(f"wrote dark-en.json: {len(s['layers'])} layers")
