# Sources

## Licensing

As of 2026-09-28, none of the four seed repos publishes a license file. The data we take is factual listing metadata (company, role title, location, application link), and each record carries `sources[]` attribution back to its origin repo. If a source owner asks for removal, open an issue, drop the source from `sources.yaml`, and remove its exclusive records.

Sources are read-only. This repo never opens issues, PRs or comments on them.

## Acceptance criteria for a new source

All must hold:
- Public data, no login wall, permissive or no-restriction terms, and no ToS or robots.txt prohibition.
- A commit in the last 30 days.
- At least 15% of its listings are new after dedupe against `data/jobs.jsonl`.
- Structure is parseable (a fixture and tests prove it).

Seed sources stay unless an issue documents abandonment.

## Monthly review

`state/last-source-review` holds the last reviewed month (`YYYY-MM`). Each review is recorded in an issue titled `Source review YYYY-MM` listing every candidate, the decision and the evidence.
