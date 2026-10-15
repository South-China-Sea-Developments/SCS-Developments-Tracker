# Harvest fixtures

`captures/` holds seven real documents fetched on 2026-10-15 (two China MFA press transcripts, one Google News headline, one AMTI analysis, one Bakamla release, one Taiwan CGA page, one Vietnam MFA statement). `recordings/` holds the extractor responses for exactly those prompts, keyed by a hash of the prompt text, so `python -m pipeline.harvest extract --recordings tests/fixtures/harvest/recordings` runs offline.

The recordings were written by hand to represent what a careful extractor returns (model field: `hand-authored-fixture`); the first live run with `--record` replaces them with real responses, and the expected candidate set in `expected_candidates.json` is then re-checked by a person. If the prompt file changes, the keys change and the recordings must be regenerated.
