"""After merging main into a run branch: main's version of every shared row wins (ticket 26).

Run branches and main both append rows to `data/*.csv`, so the merge uses git's union rule
(`.gitattributes`). Union keeps every line of both sides — right for rows only one side added, wrong for
a row both sides hold in different versions: a move main has corrected or extended since the branch was
cut (an `ongoing_through` moved forward by a continuation, a sub-region added) would then appear twice,
once stale. This rewrites each table as main has it, plus the rows of the branch whose key main lacks,
in the branch's order after main's.

    python -m pipeline.sync_data            # compares the working files with origin/main's
    python -m pipeline.sync_data --ref main
"""
from __future__ import annotations

import argparse
import csv
import io
import subprocess
from pathlib import Path

from pipeline import schema

ROOT = Path(__file__).resolve().parents[1]
KEY = {"claimants": ("code",), "moves": ("move_id",), "events": ("event_id",), "sources": ("source_id",),
       "corrections": ("move_id", "field", "new_value", "date")}


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def merged(main_rows: list[dict], working_rows: list[dict], key: tuple[str, ...]) -> list[dict]:
    """Main's rows in main's order, then the working rows whose key main does not have (first
    occurrence of each key only, so a union duplicate of a branch-only row is dropped too)."""
    k = lambda r: tuple(r.get(c, "") for c in key)
    have = {k(r) for r in main_rows}
    out = list(main_rows)
    for r in working_rows:
        if k(r) not in have:
            have.add(k(r))
            out.append(r)
    return out


def sync(data_dir: Path, ref: str = "origin/main", root: Path = ROOT) -> dict[str, int]:
    """Rewrite each table under data_dir; returns {table: rows dropped as stale or duplicate}."""
    dropped = {}
    for name, key in KEY.items():
        path = data_dir / f"{name}.csv"
        if not path.exists():
            continue
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        shown = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=root, capture_output=True, text=True)
        if shown.returncode != 0:
            continue                                   # the table is new on this branch: nothing to compare
        main_rows = _rows(shown.stdout)
        working = _rows(path.read_text(encoding="utf-8"))
        rows = merged(main_rows, working, key)
        dropped[name] = len(working) - len(rows)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=schema.TABLES[name], lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    return dropped


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ref", default="origin/main")
    p.add_argument("--data", type=Path, default=ROOT / "data")
    a = p.parse_args(argv)
    res = sync(a.data, a.ref)
    print("synced with " + a.ref + ": " + ", ".join(f"{t} {n} stale/duplicate row(s) dropped" for t, n in res.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
