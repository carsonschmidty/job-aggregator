# Changelog

## Unreleased
- Bootstrap: scaffold, parsers for Simplify and speedyapply tables, dedupe, validation, CI.
- Source: ApplyGuy/2027-Internships (MIT) with an `applyguy` parser; the original listing link is kept as `apply_url`.
- Fix: a listing matched by fuzzy match is no longer marked `closed` on the run that saw it.
- Normalize: `location` segments map `NYC`, `SF`, `LA` to `City, ST` and `Remote in X` to `Remote - X`; 464 records relocated. Fuzzy location overlap ignores `city` and two-letter codes.
- Dedupe: `scripts.dedupe` consolidates duplicates that a matcher change surfaces; first run on 2026-10-14 folded 33 cross-source pairs into their older record (removed ids listed in #38).
