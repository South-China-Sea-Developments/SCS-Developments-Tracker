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
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipeline import schema
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
            per_year[str(y)] = {**{f: sum(int(m[f]) for m in in_year) for f in schema.FLAG_COLUMNS}, "total": len(in_year)}
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


def git_describe() -> str:
    try:
        return subprocess.run(["git", "describe", "--always", "--dirty"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # not a git checkout (e.g. a downloaded bundle)
        return "unversioned"


def build(data_dir: Path, out_dir: Path, build_date: str | None = None) -> dict:
    moves = read_csv(data_dir / "moves.csv")
    claimants = read_csv(data_dir / "claimants.csv")
    events_by_move: dict[str, list[dict]] = {}
    for e in read_csv(data_dir / "events.csv"):
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
    agg["subregion_paths"] = {str(k): v for k, v in subregion_paths(data_dir / "reference" / "mavd_subregions.geojson").items()}
    agg["view"] = [VIEW_W, VIEW_H]
    agg["mats_last_year"] = schema.MATS_YEARS[-1]
    agg["coded_by_chubb"] = sum(1 for m in moves if m["coded_by"] == "chubb" and m["status"] == "accepted")
    meta = {
        "build_date": build_date or dt.date.today().isoformat(),
        "version": git_describe(),
        "dataset_version": schema.DATASET_VERSION,
        "repo_url": schema.REPO_URL,
        "n_moves": agg["n_moves"],
        "n_pending": agg["n_pending"],
        "first_year": agg["years"][0],
        "last_year": agg["years"][-1],
        "mats_last_year": schema.MATS_YEARS[-1],
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
    # the case list the browser filters client-side: one compact record per move
    index = {
        "names": names, "type_labels": TYPE_LABELS,
        "cases": [{"id": v["id"], "c": v["claimant"], "y": v["year"], "t": v["types"], "d": v["domains"],
                   "i": v["issues"], "s": v["subregions"], "g": v["targets"], "st": v["status"],
                   "x": v["description"]} for v in views],
    }
    index_json = json.dumps(index, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")

    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    ctx = {
        "meta": meta,
        "agg_json": json.dumps(agg, separators=(",", ":")).replace("</", "<\\/"),  # safe inside <script>
        "claimants": claimants,
        "types": [(t, TYPE_LABELS[t], TYPE_BLURBS[t]) for t in schema.TYPE_FLAGS],
        "subregions": list(zip(range(1, 11), schema.SUBREGION_NAMES)),
    }
    ctx.update(names=names, n_moves_all=len(views), index_json=index_json,
               subregion_paths=paths, view_w=VIEW_W, view_h=VIEW_H,
               subregion_names=dict(zip(range(1, 11), schema.SUBREGION_NAMES)),
               domain_labels=DOMAIN_LABELS, issue_labels=ISSUE_LABELS,
               dyad_targets=DYAD_NAMES)
    pages = {"index.html": "index.html", "methodology.html": "methodology.html", "cases.html": "cases.html",
             "issues-domains.html": "issues-domains.html", "subregions.html": "subregions.html"}
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
    agg = build(a.data, a.out, a.build_date)
    print(f"built {a.out}: {agg['n_moves']} moves, {agg['years'][0]}-{agg['years'][-1]}, "
          f"{len(list((a.out / 'cases').glob('*.html')))} case pages")


if __name__ == "__main__":
    main()
