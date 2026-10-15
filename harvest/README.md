# Harvest working folder

Run output lives here and is not committed (see `.gitignore`): `captures/<run_id>/<source>/*.json` (raw documents),
`runs/<run_id>/candidates.csv|sources.csv|run.json` (candidate events in the canonical schema plus cost and yield),
`recordings/<run_id>/` (the model's responses, replayable offline), `state.json` (guids already seen).

The source registry is `pipeline/sources.json`; the extraction prompt is `pipeline/prompts/extract_events.md`.
In CI, `state.json` is uploaded as an artifact but not restored, so a manual run re-captures what it lists unless `--since` is given; ticket 07 carries the state across scheduled runs by committing it in the review pull request.

Commands: `python -m pipeline.harvest probe|fetch|extract|run` (`--help` on each). A live run from CI: the
"harvest (manual)" workflow, which needs the `ANTHROPIC_API_KEY` repository secret.
