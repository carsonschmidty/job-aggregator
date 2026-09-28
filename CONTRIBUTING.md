# Contributing

1. Open an issue first (labels: `data`, `parser`, `source`, `chore`, `docs`, `bug`) with context and acceptance criteria.
2. Branch from `main`: `feat/issue-<n>` or `data/YYYY-MM-DD-<slug>`.
3. Use conventional commits: `feat(parser):`, `data:`, `fix:`, `docs:`, `test:`, `chore:`.
4. Open a PR that says `Closes #<n>`, with test evidence.
5. CI must pass (`pytest` and `scripts.validate`). Squash-merge and delete the branch.

## Rules for data changes

- Never hand-edit `data/jobs.jsonl`. Change a parser or `scripts/ingest.py`, then regenerate.
- Never add a record that `scripts.validate` rejects. Duplicates are a bug.
- Keep apply URLs, sponsorship and citizenship notes verbatim from the source.
- New sources need a `sources.yaml` entry, a parser, a fixture under `tests/fixtures/`, and tests. See `docs/SOURCES.md`.
