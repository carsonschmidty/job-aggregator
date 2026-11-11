# Changelog

## Unreleased
- Bootstrap: scaffold, parsers for Simplify and speedyapply tables, dedupe, validation, CI.
- Source: ApplyGuy/2027-Internships (MIT) with an `applyguy` parser; the original listing link is kept as `apply_url`.
- Fix: a listing matched by fuzzy match is no longer marked `closed` on the run that saw it.
- Normalize: `location` segments map `NYC`, `SF`, `LA` to `City, ST` and `Remote in X` to `Remote - X`; 464 records relocated. Fuzzy location overlap ignores `city` and two-letter codes.
- Dedupe: `scripts.dedupe` consolidates duplicates that a matcher change surfaces; first run on 2026-10-14 folded 33 cross-source pairs into their older record (removed ids listed in #38).
- Fix: SimplifyJobs cells joined with `</br>` now split into `; ` segments; an exact-id hit may add separators to a stored location so the fix reaches existing records. Regeneration consolidated 8 pairs that the repaired locations revealed (ids in #39).
- Dedupe: fuzzy match no longer pairs titles that differ only by a language or platform name (C++ vs Python, iOS vs Android); each keeps its own apply link (#40).
- Normalize: `London, United Kingdom`, `Singapore, Singapore`, `Toronto, Canada` and `Vancouver, Canada` map to the SimplifyJobs spelling (#46).
- Normalize: `USA` maps to `United States` and `<State>, USA` to the bare state name, the SimplifyJobs spelling; 71 records relocated, 0 merged (#54).
- Fix: ingest consolidates fuzzy pairs that an exact-id location rewrite creates; the 2026-10-28 ingest removed `76c81f95ca2f5cdf` (KBR, into `2c422c69f8598f84`) and `c3566e635db47e56` (True Anomaly, into `39f37d6c7002ee8f`) (#61, #62).
- Source: vanshb03/Summer2027-Internships (MIT) with a `vansh` parser; the `go.vansh.nyc` redirect is kept verbatim as `apply_url`, so cross-source matches rely on the fuzzy path (#73).
- Dedupe: `scripts.report` writes `docs/shared-apply-urls.md`, the open records that share a canonical apply URL under different ids, grouped by company relation; store unchanged (#90, #68).
- Normalize: `<City>, United Kingdom` maps to `<City>, UK` and `Remote - United Kingdom` to `Remote - UK`, the SimplifyJobs spelling; `+N` cells unchanged; 151 records relocated, 0 merged (#99).
- Ingest: the JSON summary lists each consolidation's removed and surviving id under `consolidated_ids`, next to the `consolidated` count (#103).
- Ingest: the JSON summary counts stored records whose `status` went from `closed` back to `open` under `reopened`; the contract says `closed` is not terminal (#107).
