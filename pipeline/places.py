"""Suggest the sub-regions of a candidate from what it says about its place (ticket 33).

A candidate often names no reef: "off Sabah and Sarawak", "the Bruneian EEZ", "Block K". The gazetteer
places features; this module adds the named areas of data/reference/areas.csv (coastal bands, EEZs,
seas, oil blocks, each with its share of the ten sub-regions) and returns the sub-regions with the
reason for each, for the coder to accept or trim. It suggests; it never writes a sub-region itself.

Order of trust: the event's own coordinates; the features and areas its place names; then, only if
the place gives nothing, those its summary names. An area's sub-regions are those holding at least
MIN_SHARE of it, largest first; a broad area (an EEZ) counts only when nothing narrower is named.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from pipeline import gazetteer, schema

AREAS = gazetteer.GAZETTEER.parent / "areas.csv"
MIN_SHARE = 0.15
BROAD = {"eez"}


@lru_cache(maxsize=2)
def _areas(path: Path = AREAS) -> list[tuple[str, dict]]:
    """(folded name, area) for every name and alias, longest first."""
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        r["shares"] = [(int(n), float(v)) for n, v in (x.split(":") for x in r["shares"].split("|") if x)]
        for n in [r["name"], *[a for a in r["aliases"].split("|") if a]]:
            out.append((gazetteer._fold(n), r))
    return sorted(out, key=lambda t: -len(t[0]))


def _area_hits(text: str) -> list[tuple[int, dict, str]]:
    """(position, area, the name as matched) for the areas `text` names, longest names first, no overlaps."""
    folded = gazetteer._fold(text or "")
    taken, hits = [], []
    for name, area in _areas():
        for m in re.finditer(r"(?<![\w'’])" + re.escape(name) + r"(?![\w'’])", folded):
            a, b = m.span()
            if any(a < y and x < b for x, y in taken):
                continue
            taken.append((a, b))
            hits.append((a, area, text[a:b] if len(folded) == len(text) else area["name"]))
    return sorted(hits, key=lambda t: t[0])


def _from_text(text: str) -> list[tuple[int, str]]:
    """(sub-region, basis) from the features and areas `text` names, in order of mention."""
    out: list[tuple[int, str]] = []
    feats = gazetteer.named_features(text)
    for f in feats:
        sr = f["subregion"] or gazetteer.subregion_of(f["lat"], f["lon"])
        if sr:
            out.append((int(sr), f["name_en"]))
    group = gazetteer.resolve(text)
    if group and group["kind"] == "island group" and group["subregion"]:
        out.append((int(group["subregion"]), group["name_en"]))
    hits = _area_hits(text)
    narrow = [h for h in hits if h[1]["kind"] not in BROAD]
    for _, area, said in (narrow if (narrow or out) else hits):
        kept = [(n, v) for n, v in area["shares"] if v >= MIN_SHARE] or area["shares"][:1]
        for n, v in kept:
            label = area["name"] + (" coast" if area["kind"] == "coast" else "")
            out.append((n, label if v >= 0.995 else f"{label} {round(v * 100)}%"))
    return out


def suggest_subregions(event: dict) -> list[dict]:
    """[{"subregion": n, "name": ..., "basis": "..."}], most supported first; [] when nothing places it."""
    if event.get("lat") and event.get("lon"):
        try:
            sr = gazetteer.subregion_of(float(event["lat"]), float(event["lon"]))
        except (TypeError, ValueError):
            sr = None
        if sr:
            return [{"subregion": sr, "name": schema.SUBREGION_NAMES[sr - 1], "basis": "its coordinates"}]
    found = _from_text(event.get("location_name", "")) or _from_text(event.get("summary", ""))
    merged: dict[int, list[str]] = {}
    for n, basis in found:
        merged.setdefault(n, [])
        if basis not in merged[n]:
            merged[n].append(basis)
    order = sorted(merged, key=lambda n: (-len(merged[n]), [x for x, _ in found].index(n)))
    return [{"subregion": n, "name": schema.SUBREGION_NAMES[n - 1], "basis": "; ".join(merged[n])} for n in order]


def note(suggestions: list[dict]) -> str:
    """One line for the coder: 'Sub-regions suggested: 10 Far South (Sarawak coast); 7 ...'."""
    if not suggestions:
        return ""
    return "Sub-regions suggested: " + "; ".join(f"{s['subregion']} {s['name']} ({s['basis']})" for s in suggestions) + "."
