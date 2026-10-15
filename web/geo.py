"""Sub-region polygons as compact SVG paths for the inset map on move pages.

Equirectangular projection of the MAVD polygons into a fixed viewBox, simplified with
Douglas-Peucker so the ten shapes cost a few kilobytes inline per page.
"""
from __future__ import annotations

import json
from pathlib import Path

LON_MIN, LON_MAX = 106.5, 120.0
LAT_MIN, LAT_MAX = 2.5, 21.5
VIEW_W = 240
VIEW_H = round(VIEW_W * (LAT_MAX - LAT_MIN) / (LON_MAX - LON_MIN))   # same scale on both axes


def project(lon: float, lat: float) -> tuple[float, float]:
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * VIEW_W
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * VIEW_H
    return x, y


def _perp_dist(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def simplify(points: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Douglas-Peucker on an open polyline (the ring's closing point is handled by the caller)."""
    if len(points) < 3:
        return points
    a, b = points[0], points[-1]
    idx, dmax = 0, 0.0
    for i in range(1, len(points) - 1):
        d = _perp_dist(points[i], a, b)
        if d > dmax:
            idx, dmax = i, d
    if dmax <= tol:
        return [a, b]
    left = simplify(points[: idx + 1], tol)
    right = simplify(points[idx:], tol)
    return left[:-1] + right


def subregion_paths(geojson_path: Path, tol_deg: float = 0.02) -> dict[int, str]:
    """{LocationNo: 'M.. L.. Z'} in viewBox units, rounded to one decimal."""
    g = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    out = {}
    for f in g["features"]:
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        parts = []
        for poly in polys:
            ring = [(float(c[0]), float(c[1])) for c in poly[0]]
            if ring[0] == ring[-1]:
                ring = ring[:-1]
            # simplify as two halves so the ring's start point is not privileged
            half = len(ring) // 2
            simp = simplify(ring[: half + 1], tol_deg)[:-1] + simplify(ring[half:] + [ring[0]], tol_deg)[:-1]
            pts = [project(lon, lat) for lon, lat in simp]
            parts.append("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z")
        out[int(f["properties"]["LocationNo"])] = " ".join(parts)
    return out
