"""Build the public site as a self-contained static bundle from the canonical files.

Reads data/*.csv, computes the chart aggregates, renders the templates and copies static
assets into the output folder. Relative paths only: the bundle works from any host or from disk.

Usage: python -m web.build [--data data] [--out web/dist]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipeline import agreement, release, schema
from pipeline.load_mats import SEED_RUN
from web.geo import VIEW_H, VIEW_W, subregion_paths

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent

DYAD_NAMES = {"R": "Taiwan (ROC)", "C": "China (PRC)", "P": "Philippines", "V": "Vietnam", "M": "Malaysia",
              "B": "Brunei", "I": "Indonesia", "A": "all claimants", "U": "unclear"}
DOMAIN_LABELS = schema.DOMAIN_LABELS
ISSUE_LABELS = schema.ISSUE_LABELS
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]

TYPE_LABELS = schema.TYPE_LABELS
TYPE_BLURBS = {
    "declarative": "Verbal assertions via non-coercive statements, diplomatic protests, legislation.",
    "demonstrative": "Unilateral administration of disputed possessions without confrontation: patrols, surveys, "
                     "resource development, construction, state-sanctioned tourism or activism, domestic judicial "
                     "proceedings, cooperative agreements with third parties.",
    "coercive": "Threat or imposition of punishment: verbal, diplomatic, administrative or economic punishment, "
                "warning shots, physical interference with foreign activities in disputed areas.",
    "force": "Application of military force, or direct seizure and occupation of a disputed possession.",
}


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def compute_aggregates(moves: list[dict]) -> dict:
    """The site's own computation of the chart numbers (the validator has an independent one)."""
    accepted = [m for m in moves if m["status"] == "accepted"]
    years = list(range(1970, max([int(m["year"]) for m in accepted] + [1970]) + 1))
    dims = schema.TYPE_FLAGS + schema.DOMAIN_FLAGS + schema.ISSUE_FLAGS
    by_claimant = {}
    for code in schema.CLAIMANT_CODES:
        mine = [m for m in accepted if m["claimant"] == code]
        per_year = {}
        for y in years:
            in_year = [m for m in mine if m["year"] == str(y)]
            per_year[str(y)] = {**{f: sum(int(m[f]) for m in in_year) for f in dims}, "total": len(in_year)}
        per_loc, loc_years = {}, {}
        for i, loc in enumerate(schema.SUBREGION_FLAGS, start=1):
            in_loc = [m for m in mine if m[loc] == "1"]
            per_loc[str(i)] = {**{f: sum(int(m[f]) for m in in_loc) for f in dims}, "total": len(in_loc)}
            loc_years[str(i)] = {}
            for y in sorted({m["year"] for m in in_loc}, key=int):
                in_y = [m for m in in_loc if m["year"] == y]
                loc_years[str(i)][y] = {**{t: sum(int(m[t]) for m in in_y) for t in schema.TYPE_FLAGS}, "total": len(in_y)}
        totals = {**{f: sum(int(m[f]) for m in mine) for f in schema.FLAG_COLUMNS}, "total": len(mine)}
        by_claimant[code] = {"years": per_year, "totals": totals, "subregions": per_loc, "subregion_years": loc_years}
    return {"years": years, "types": list(schema.TYPE_FLAGS), "domains": list(schema.DOMAIN_FLAGS),
            "issues": list(schema.ISSUE_FLAGS), "subregions": list(schema.SUBREGION_FLAGS),
            "claimants": list(schema.CLAIMANT_CODES),
            "n_moves": len(accepted), "n_pending": sum(1 for m in moves if m["status"] == "pending"),
            "by_claimant": by_claimant}

def dyad_label(code: str) -> str:
    """'CV' -> 'China (PRC) → Vietnam'; 'A' -> 'all claimants'."""
    if len(code) == 2:
        return f"{DYAD_NAMES.get(code[0], code[0])} → {DYAD_NAMES.get(code[1], code[1])}"
    return DYAD_NAMES.get(code, code)


def date_label(start: str, end: str, precision: str) -> str:
    """ISO dates -> what a reader expects: '29 January 1973', 'May 1971', '1974'."""
    y, mo, d = start[:4], int(start[5:7] or 1), int(start[8:10] or 1)
    if precision == "day":
        return f"{d} {MONTHS[mo - 1]} {y}"
    if precision == "month":
        return f"{MONTHS[mo - 1]} {y}"
    return y


def event_view(e: dict, move_year: int, sources: list[dict]) -> dict:
    """An event with the facts the page branches on computed from data, not from prose."""
    return dict(
        e,
        sources=sources,
        is_seed=e["harvest_run_id"] == SEED_RUN,
        approximate=e["summary"].startswith("Approximate date."),
        outside_year=bool(e["date_start"]) and int(e["date_start"][:4]) != move_year,
        date_label=date_label(e["date_start"], e["date_end"], e["date_precision"]) if e["date_start"] else "undated",
    )


def latest_developments(events: list[dict], moves: list[dict], names: dict, n: int = 8) -> list[dict]:
    """The newest accepted events, newest first, one row per move (its newest event), for the home
    page: date and precision, claimant, the event's own summary when the project coded it, otherwise
    its move's description (a MATS-era seed event has only a mechanical summary), the move to link to,
    and whether the coding is the project's."""
    move_by_id = {m["move_id"]: m for m in moves}
    rows = []
    for e in events:
        m = move_by_id.get(e["move_id"])
        if e["status"] != "accepted" or not e["date_start"] or not m or m["status"] != "accepted":
            continue
        own = bool(e.get("extractor")) or m["coded_by"] != "chubb"
        text = e["summary"] if own else m["description"]
        rows.append({"event_id": e["event_id"], "move_id": m["move_id"], "claimant": e["claimant"], "claimant_name": names.get(e["claimant"], e["claimant"]),
                     "date": e["date_start"], "date_precision": e["date_precision"], "date_label": date_label(e["date_start"], e["date_start"], e["date_precision"]),
                     "text": text[:280].rsplit(" ", 1)[0] + "…" if len(text) > 280 else text, "location": e["location_name"],
                     "types": [t for t in schema.TYPE_FLAGS if m[t] == "1"], "project": m["coded_by"] != "chubb"})
    rows.sort(key=lambda r: (r["date"], r["event_id"]), reverse=True)
    seen, out = set(), []
    for r in rows:
        if r["move_id"] in seen:
            continue
        seen.add(r["move_id"])
        out.append(r)
    return out[:n]


def move_view(m: dict, events_by_move: dict, sources_by_event: dict) -> dict:
    """Everything a move page or list row needs, with codes expanded to labels."""
    types = [t for t in schema.TYPE_FLAGS if m[t] == "1"]
    domains = [d for d in schema.DOMAIN_FLAGS if m[d] == "1"]
    issues = [i for i in schema.ISSUE_FLAGS if m[i] == "1"]
    subregions = [i + 1 for i, f in enumerate(schema.SUBREGION_FLAGS) if m[f] == "1"]
    dyads = m["dyads"].split()
    year = int(m["year"])
    evs = sorted(events_by_move.get(m["move_id"], []), key=lambda e: (e["date_start"], e["event_id"]))
    return {
        "id": m["move_id"], "claimant": m["claimant"], "year": year,
        "types": types, "type_labels": [TYPE_LABELS[t] for t in types],
        "type_pairs": [(t, TYPE_LABELS[t]) for t in types],
        "domains": domains, "domain_labels": [DOMAIN_LABELS[d] for d in domains],
        "issues": issues, "issue_labels": [ISSUE_LABELS[i] for i in issues],
        "subregions": subregions, "subregion_labels": [schema.SUBREGION_NAMES[i - 1] for i in subregions],
        "dyads": dyads, "dyad_labels": [dyad_label(d) for d in dyads],
        "targets": sorted({d[1] for d in dyads if len(d) == 2}),
        "description": m["description"],
        "ongoing_through": m["ongoing_through"], "ongoing_through_notes": m["ongoing_through_notes"],
        "diminished_notes": m["diminished_notes"], "other_possible_cases": m["other_possible_cases"],
        "intensification_criterion": m["intensification_criterion"], "org_case_no": m["org_case_no"],
        "coded_by": m["coded_by"], "coder": m["coder"], "data_version": m["data_version"], "status": m["status"],
        "events": [event_view(e, year, sources_by_event.get(e["event_id"], [])) for e in evs],
    }


def periods(years: list[int]) -> list[dict]:
    """The map's periods: the first year alone, then five-year bins, extending as years are added.

    [1970, 1971-75, ..., 2011-15, 2016-20, 2021-25, 2026] for 1970..2026; a trailing bin shorter
    than five years is labelled by its actual span (a single year by that year alone).
    """
    out = [{"key": "all", "label": "All years", "years": list(years)}]
    if not years:
        return out
    first, last = years[0], years[-1]
    out.append({"key": str(first), "label": str(first), "years": [first]})
    start = first + 1
    while start <= last:
        end = min(start + 4, last)
        span = [y for y in years if start <= y <= end]
        label = str(start) if start == end else f"{start}–{str(end)[2:]}"
        out.append({"key": f"{start}-{end}", "label": label, "years": span})
        start += 5
    return out


def map_subregions(e: dict, move: dict) -> list[str]:
    """Where an event without coordinates counts: its own sub-region, else every sub-region of its
    move. pipeline.validate.event_aggregates computes the same numbers another way (seam 3)."""
    if e["subregion"]:
        return [e["subregion"]]
    return [str(i + 1) for i, f in enumerate(schema.SUBREGION_FLAGS) if move[f] == "1"]


def date_end_for(e: dict, year: str) -> str:
    """The last day an event is shown for: its date_end, else the end of its month or year when
    that is its precision, else its start day."""
    start = e["date_start"] or f"{year}-01-01"
    end = e["date_end"] or start
    precision = e["date_precision"] or ("year" if not e["date_start"] else "day")
    if precision == "year":
        return max(end, start[:4] + "-12-31")
    if precision == "month":
        y, mth = int(start[:4]), int(start[5:7])
        last = (dt.date(y + (mth == 12), mth % 12 + 1, 1) - dt.timedelta(days=1)).isoformat()
        return max(end, last)
    return end


def map_data(events: list[dict], moves: list[dict], sources_by_event: dict) -> dict:
    """What the event map draws: accepted events of accepted moves, as points when they have
    coordinates and as sub-region counts otherwise, with the move's coding for the filters."""
    move_by_id = {m["move_id"]: m for m in moves if m["status"] == "accepted"}
    out = []
    counts = {"n_events": 0, "n_points": 0, "by_claimant": {c: {"events": 0, "points": 0, "subregions": {str(i): 0 for i in range(1, 11)}, "years": {}}
                                                             for c in schema.CLAIMANT_CODES}}
    for e in sorted(events, key=lambda e: (e["date_start"], e["event_id"])):
        m = move_by_id.get(e["move_id"])
        if e["status"] != "accepted" or m is None:
            continue
        cc = counts["by_claimant"][e["claimant"]]
        counts["n_events"] += 1
        cc["events"] += 1
        y = e["date_start"][:4] or m["year"]
        cc["years"][y] = cc["years"].get(y, 0) + 1
        rec = {"id": e["event_id"], "m": m["move_id"], "c": e["claimant"], "y": int(m["year"]),
               "ds": e["date_start"] or f"{m['year']}-01-01", "de": date_end_for(e, m["year"]), "dp": e["date_precision"] or "year",
               "s": e["summary"][:400], "n": e["location_name"], "lp": e["location_precision"] or "unknown",
               "t": [t for t in schema.TYPE_FLAGS if m[t] == "1"], "d": [d for d in schema.DOMAIN_FLAGS if m[d] == "1"],
               "i": [i for i in schema.ISSUE_FLAGS if m[i] == "1"], "g": sorted({d[1] for d in m["dyads"].split() if len(d) == 2}),
               "src": len(sources_by_event.get(e["event_id"], [])), "seed": e["harvest_run_id"] == SEED_RUN}
        if e["lat"] and e["lon"]:
            rec["lat"], rec["lon"] = round(float(e["lat"]), 4), round(float(e["lon"]), 4)
            cc["points"] += 1
            counts["n_points"] += 1
        else:
            rec["sr"] = map_subregions(e, m)
            for sr in rec["sr"]:
                cc["subregions"][sr] += 1
        out.append(rec)
    return {"events": out, "counts": counts}


def slim_geojson(gj: dict) -> dict:
    """The ten polygons with only their number and name, coordinates to 4 decimals (~11 m)."""
    def rnd(c):
        return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 4), round(c[1], 4)]
    feats = [{"type": "Feature", "properties": {"n": int(f["properties"]["LocationNo"]), "name": f["properties"]["Location_Name"]},
              "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"])}} for f in gj["features"]]
    return {"type": "FeatureCollection", "features": sorted(feats, key=lambda f: f["properties"]["n"])}


FILE_WHAT = {
    "claimants.csv": "Claimant codes and names.",
    "moves.csv": "One row per move: Type, Domain, Issue and sub-region flags, dyads, description, ongoing-through, provenance.",
    "events.csv": "One row per event: dates, place, summary, status, machine suggestions, review and harvest provenance.",
    "sources.csv": "One row per source per event: URL, title, publisher, date, excerpt.",
    "corrections.csv": "Documented corrections to MATS-era rows.",
    "mavd_subregions.geojson": "The ten MAVD sub-region polygons (WGS84).",
    "gazetteer.csv": "Named features with coordinates and sub-region, from Wikidata.",
    "gazetteer_extra.csv": "The project's additions and corrections to the gazetteer.",
    **{f"BASELINE-{c}.md": f"{n}: pre-1970 baseline actions, with sources." for c, n in (("CN", "China"), ("VN", "Vietnam"), ("PH", "Philippines"), ("MY", "Malaysia"), ("ID", "Indonesia"), ("TW", "Taiwan"))},
    "COLUMNS.md": "Column definitions of every table (data/README.md at this version).",
    "SPEC.md": "The project specification at this version.",
    "CODEBOOK-chubb-2021-appendix.txt": "Andrew Chubb's methodology appendix: the coding rules (CC0).",
    "CHANGELOG.md": "What each version changed.",
    "CITATION.cff": "Machine-readable citation for this version.",
    "README.txt": "What the files are and how to cite.",
    "SHA256SUMS": "Checksums of every file here.",
}


def size_label(n: int) -> str:
    return f"{n / 1_000_000:.1f} MB" if n >= 1_000_000 else f"{n / 1000:.0f} KB" if n >= 1000 else f"{n} B"


def notes_html(md: str) -> str:
    """CHANGELOG prose (paragraphs, '- ' bullets, `code`) as HTML; anything else is left as text."""
    import html as h
    def inline(t):
        return re.sub(r"`([^`]+)`", lambda m: "<code>" + m.group(1) + "</code>", h.escape(t))
    out, para, items = [], [], []
    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>"); para.clear()
        if items:
            out.append("<ul>" + "".join("<li>" + inline(i) + "</li>" for i in items) + "</ul>"); items.clear()
    for line in md.splitlines():
        if line.startswith("- "):
            if para:
                flush()
            items.append(line[2:].strip())
        elif not line.strip():
            flush()
        else:
            if items:
                flush()
            para.append(line.strip())
    flush()
    return "\n".join(out)


def citation(version: str, tag: str, date: str, build_date: str) -> dict:
    year = date[:4]
    accessed = f"accessed {build_date}" if tag == "unreleased" else f"released {date[:10]}"
    text = (f"South-China-Sea-Developments project (Angelo M., maintainer) ({year}). SCS Developments Tracker: assertive moves by claimant states "
            f"in the South China Sea, 1970 onward. Dataset version {version} ({accessed}). {schema.REPO_URL}. "
            f"A continuation of Chubb, A. (2022), Maritime Assertiveness Time Series (MATS 1.02).")
    key = "scs_developments_tracker_" + re.sub(r"[^0-9a-z]+", "_", version.lower()).strip("_")
    bibtex = (f"@misc{{{key},\n  author = {{{{South-China-Sea-Developments project}} and M., Angelo}},\n"
              f"  title = {{SCS Developments Tracker: assertive moves by claimant states in the South China Sea, 1970 onward}},\n"
              f"  year = {{{year}}},\n  howpublished = {{Dataset, version {version}, \\url{{{schema.REPO_URL}}}}},\n"
              f"  note = {{A continuation of Andrew Chubb's Maritime Assertiveness Time Series (MATS 1.02); cite Chubb (2021, 2022) alongside}}\n}}")
    return {"text": text, "bibtex": bibtex}


def release_context(root: Path, data_dir: Path, out_dir: Path, build_date: str) -> dict:
    """The downloads/ folder and what the Downloads page says about it: the latest reachable tag's
    files when there is one, else the working files labelled unreleased."""
    tag = release.latest_tag(root)
    if tag:
        m = release.build_assets(root, tag, out_dir / "downloads")
        notes = release.changelog_section(tag, text=release.file_at(root, tag, "CHANGELOG.md").decode("utf-8"))
    else:
        m = release.working_assets(data_dir, out_dir / "downloads", date=build_date + "T00:00:00+00:00", root=root)
        notes = ""
    for f in m["files"]:
        f["what"] = FILE_WHAT.get(f["name"], "")
        f["size_label"] = size_label(f["bytes"])
    m["zip"]["size_label"] = size_label(m["zip"]["bytes"])
    m["notes"] = notes
    m["notes_html"] = notes_html(notes)
    m["prerelease"] = "-" in m["tag"]
    return m


def git_describe(root: Path = ROOT) -> str:
    try:
        return subprocess.run(["git", "describe", "--always", "--dirty"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # not a git checkout (e.g. a downloaded bundle)
        return "unversioned"


def build(data_dir: Path, out_dir: Path, build_date: str | None = None, repo: Path = ROOT) -> dict:
    moves = read_csv(data_dir / "moves.csv")
    claimants = read_csv(data_dir / "claimants.csv")
    events = read_csv(data_dir / "events.csv")
    events_by_move: dict[str, list[dict]] = {}
    for e in events:
        events_by_move.setdefault(e["move_id"], []).append(e)
    sources_by_event: dict[str, list[dict]] = {}
    for s in read_csv(data_dir / "sources.csv"):
        sources_by_event.setdefault(s["event_id"], []).append(s)
    names = {c["code"]: c["name"] for c in claimants}
    views = [move_view(m, events_by_move, sources_by_event) for m in sorted(moves, key=lambda m: (m["year"], m["move_id"]))]
    paths = subregion_paths(data_dir / "reference" / "mavd_subregions.geojson")
    agg = compute_aggregates(moves)
    agg["claimant_names"] = names
    agg["type_labels"] = TYPE_LABELS
    agg["domain_labels"] = DOMAIN_LABELS
    agg["issue_labels"] = ISSUE_LABELS
    agg["subregion_names"] = dict(zip((str(i) for i in range(1, 11)), schema.SUBREGION_NAMES))
    agg["subregion_paths"] = {str(k): v for k, v in paths.items()}
    agg["view"] = [VIEW_W, VIEW_H]
    agg["periods"] = periods(agg["years"])
    agg["mats_last_year"] = schema.MATS_YEARS[-1]
    agg["coded_by_chubb"] = sum(1 for m in moves if m["coded_by"] == "chubb" and m["status"] == "accepted")
    meta = {
        "build_date": build_date or dt.date.today().isoformat(),
        "version": git_describe(repo),
        "dataset_version": schema.DATASET_VERSION,
        "repo_url": schema.REPO_URL,
        "n_moves": agg["n_moves"],
        "n_pending": agg["n_pending"],
        "first_year": agg["years"][0],
        "last_year": agg["years"][-1],
        "mats_last_year": schema.MATS_YEARS[-1],
        "n_claimants_coded": sum(1 for c, v in agg["by_claimant"].items() if sum(y["total"] for y in v["years"].values())),
        "n_claimants": len(claimants),
    }

    out_dir = Path(out_dir).resolve()
    marker = out_dir / ".site-build"
    if out_dir == ROOT or ROOT.is_relative_to(out_dir):
        raise SystemExit(f"refusing to build into {out_dir}: it contains the repository")
    if out_dir.exists():
        if any(out_dir.iterdir()) and not marker.exists():
            raise SystemExit(f"refusing to clear {out_dir}: not a previous site build (no .site-build marker)")
        shutil.rmtree(out_dir)
    (out_dir / "data").mkdir(parents=True)
    (out_dir / "cases").mkdir()
    marker.write_text("written by web.build; this folder is cleared on every build\n", encoding="utf-8")
    shutil.copytree(HERE / "static", out_dir / "assets")
    (out_dir / "data" / "aggregates.json").write_text(json.dumps(agg, indent=1), encoding="utf-8")
    agree = agreement.report(events, moves)
    (out_dir / "data" / "agreement.json").write_text(json.dumps(agree, indent=1), encoding="utf-8")
    # the case list the browser filters client-side: one compact record per move
    index = {
        "names": names, "type_labels": TYPE_LABELS,
        "cases": [{"id": v["id"], "c": v["claimant"], "y": v["year"], "t": v["types"], "d": v["domains"],
                   "i": v["issues"], "s": v["subregions"], "g": v["targets"], "st": v["status"], "cb": v["coded_by"],
                   "x": v["description"]} for v in views],
    }
    index_json = json.dumps(index, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    mapd = map_data(events, moves, sources_by_event)
    mapd["subregions"] = slim_geojson(json.loads((data_dir / "reference" / "mavd_subregions.geojson").read_text(encoding="utf-8")))
    mapd["names"] = names
    mapd["type_labels"] = TYPE_LABELS
    mapd["subregion_names"] = dict(zip((str(i) for i in range(1, 11)), schema.SUBREGION_NAMES))
    mapd["first_year"], mapd["last_year"] = agg["years"][0], agg["years"][-1]
    (out_dir / "data" / "events.json").write_text(json.dumps(mapd, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    map_json = json.dumps(mapd, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    map_style_json = (HERE / "static" / "vendor" / "openfreemap" / "positron-en.json").read_text(encoding="utf-8").replace("</", "<\\/")

    rel = release_context(repo, data_dir, out_dir, meta["build_date"])
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    ctx = {
        "release": rel,
        "citation": citation(rel["version"], rel["tag"], rel["date"], meta["build_date"]),
        "meta": meta,
        "agg_json": json.dumps(agg, separators=(",", ":")).replace("</", "<\\/"),  # safe inside <script>
        "claimants": claimants,
        "types": [(t, TYPE_LABELS[t], TYPE_BLURBS[t]) for t in schema.TYPE_FLAGS],
        "subregions": list(zip(range(1, 11), schema.SUBREGION_NAMES)),
    }
    ctx.update(names=names, n_moves_all=len(views), index_json=index_json, latest=latest_developments(events, moves, names), agreement=agree, agreement_labels=agreement.LABELS, map_json=map_json, map_style_json=map_style_json,
               n_map_events=mapd["counts"]["n_events"], n_map_points=mapd["counts"]["n_points"],
               subregion_paths=paths, view_w=VIEW_W, view_h=VIEW_H,
               subregion_names=dict(zip(range(1, 11), schema.SUBREGION_NAMES)),
               domain_labels=DOMAIN_LABELS, issue_labels=ISSUE_LABELS,
               dyad_targets=DYAD_NAMES)
    pages = {"index.html": "index.html", "methodology.html": "methodology.html", "cases.html": "cases.html",
             "issues-domains.html": "issues-domains.html", "subregions.html": "subregions.html", "map.html": "map.html",
             "downloads.html": "downloads.html"}
    for out_name, tmpl in pages.items():
        html = env.get_template(tmpl).render(page=out_name, root="", **ctx)
        (out_dir / out_name).write_text(html, encoding="utf-8")
    case_tmpl = env.get_template("case.html")
    for v in views:
        html = case_tmpl.render(page="case", root="../", move=v, **ctx)
        (out_dir / "cases" / f"{v['id']}.html").write_text(html, encoding="utf-8")
    return agg


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=ROOT / "data")
    p.add_argument("--out", type=Path, default=ROOT / "web" / "dist")
    p.add_argument("--build-date", default=None)
    a = p.parse_args(argv)
    if a.build_date:
        try:
            dt.date.fromisoformat(a.build_date)
        except ValueError:
            p.error(f"--build-date {a.build_date!r} is not YYYY-MM-DD")
    agg = build(a.data, a.out, a.build_date)
    print(f"built {a.out}: {agg['n_moves']} moves, {agg['years'][0]}-{agg['years'][-1]}, "
          f"{len(list((a.out / 'cases').glob('*.html')))} case pages")


if __name__ == "__main__":
    main()
