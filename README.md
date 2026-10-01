# job-aggregator

One deduplicated, schema-stable store of 2027 internship and new-grad listings, aggregated from public GitHub job lists. Built so downstream agents can read a single file instead of four READMEs.

Data lives in [`data/jobs.jsonl`](data/jobs.jsonl): one JSON object per line.

## Sources

| Source | Content |
|---|---|
| [SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships) | Internships by category |
| [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions) | New grad by category |
| [speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs) | SWE internships and new grad, USA and international |
| [speedyapply/2027-AI-College-Jobs](https://github.com/speedyapply/2027-AI-College-Jobs) | AI/ML internships and new grad, USA and international |
| [ApplyGuy/2027-Internships](https://github.com/ApplyGuy/2027-Internships) | Internships, MIT licensed; category inferred from title, may be null |

All listings are attributed to their origin in each record's `sources[]`. The registry is [`sources.yaml`](sources.yaml); see [`docs/SOURCES.md`](docs/SOURCES.md) for licensing notes and the monthly source-review policy.

## Consumer contract (schema_version 1)

Records are updated in place by `id`. Records are never deleted; a listing that disappears from every source gets `status: "closed"`.

| Field | Type | Notes |
|---|---|---|
| `id` | string | 16 hex chars of sha256(normalized company + title + canonical apply URL) |
| `company`, `title`, `location` | string | As published; multi-location rows are joined with `; ` |
| `apply_url` | string | Direct application link, tracking params intact |
| `url` | string | Detail page if the source offers one, else `apply_url` |
| `sources` | array | `[{source, source_url}]`, one entry per feeder listing it |
| `category` | string or null | `swe`, `pm`, `ai_ml_data`, `quant`, `hardware`; null when the source gives no category and the title is ambiguous |
| `job_type` | string | `internship` or `new_grad` |
| `first_seen`, `last_seen` | date | ISO dates |
| `status` | string | `open` or `closed` |
| `sponsorship` | string or null | `no_sponsorship` when the source flags it |
| `citizenship` | string or null | `us_citizenship_required` when the source flags it |
| `salary` | string or null | Verbatim from source when present |
| `schema_version` | int | Bumped on breaking changes |

Duplicates are prevented by an exact id check plus a fuzzy match (same company and job type, title similarity at least 0.9, overlapping location). `python -m scripts.validate` fails on either.

## Usage

```bash
pip install -r requirements.txt
python -m scripts.ingest      # fetch all sources, merge, close vanished listings
python -m scripts.validate    # schema + duplicate check (also runs in CI)
python -m pytest -q
```

A source whose row count moves more than 30% between runs is skipped for that run and needs a maintainer to look at it (see `scripts/ingest.py`).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
