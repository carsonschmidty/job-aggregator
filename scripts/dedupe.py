"""Re-normalize locations across the store and consolidate fuzzy duplicates.

Usage:
    python -m scripts.dedupe            # rewrite data/jobs.jsonl, print a JSON summary
    python -m scripts.dedupe --dry-run  # print the summary only

Run this after a change to `normalize_location` or `is_fuzzy_match` makes existing records
match each other. Ingest calls `consolidate` on every run as well, because an id hit that
splits a run-together location can make two stored records match (#61).
"""
from __future__ import annotations

import argparse
import json

from .common import is_fuzzy_match, load_store, normalize, normalize_location, save_store


def consolidate(store: list[dict]) -> tuple[list[dict], dict]:
    """Return (surviving records, summary). Pairs merge into the record seen first."""
    relocated = 0
    for r in store:
        loc = normalize_location(r["location"])
        relocated += loc != r["location"]
        r["location"] = loc
    merged: list[dict] = []
    by_company: dict[str, list[dict]] = {}
    for rec in sorted(store, key=lambda r: (r["first_seen"], r["id"])):
        group = by_company.setdefault(normalize(rec["company"]), [])
        hit = next((c for c in group if is_fuzzy_match(rec, c)), None)
        if hit is None:
            group.append(rec)
            continue
        known = {s["source"] for s in hit["sources"]}
        hit["sources"] += [s for s in rec["sources"] if s["source"] not in known]
        hit["last_seen"] = max(hit["last_seen"], rec["last_seen"])
        if rec["status"] == "open":
            hit["status"] = "open"
        if hit.get("category") is None:
            hit["category"] = rec.get("category")
        merged.append({"removed": rec["id"], "into": hit["id"], "company": rec["company"], "title": rec["title"]})
    survivors = [r for g in by_company.values() for r in g]
    return survivors, {"relocated": relocated, "merged": merged, "total": len(survivors)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    survivors, summary = consolidate(load_store())
    if not args.dry_run:
        save_store(survivors)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
