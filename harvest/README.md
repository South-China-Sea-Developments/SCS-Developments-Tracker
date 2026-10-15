# Harvest working folder

Run output lives here and is not committed (see `.gitignore`): `captures/<run_id>/<source>/*.json` (raw documents),
`runs/<run_id>/candidates.csv|sources.csv|run.json` (candidate events in the canonical schema plus cost and yield),
`recordings/<run_id>/` (the model's responses, replayable offline), `state.json` (guids already seen).

The source registry is `pipeline/sources.json`; the extraction prompt is `pipeline/prompts/extract_events.md`.
`state.json` (guids already captured) is restored from and saved to the `harvest-state` branch by the scheduled run (`python -m pipeline.ops state pull|push`); a local run can do the same, or use `--since` to bound itself.

Commands: `python -m pipeline.harvest probe|fetch|extract|run` (`--help` on each). The scheduled run is the
"harvest" workflow (Mondays, or dispatch it by hand, with a dry-run option); it needs the `ANTHROPIC_API_KEY` repository secret.
Operations around it (state branch, failure issue, reminders): `python -m pipeline.ops` (`--help`).
