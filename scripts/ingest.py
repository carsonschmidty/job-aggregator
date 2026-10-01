"""Fetch sources, parse, dedupe-merge into data/jobs.jsonl.

Usage:
    python -m scripts.ingest                 # fetch live, merge everything
    python -m scripts.ingest --sample 0.9    # bootstrap: ingest a deterministic ~90%
    python -m scripts.ingest --offline DIR   # read pre-fetched files (tests, replays)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

import yaml

from .common import ROOT, SCHEMA_VERSION, is_fuzzy_match, load_store, make_id, normalize, save_store
from .parsers import parse_applyguy, parse_simplify, parse_speedyapply

UA = "job-aggregator/0.1 (+https://github.com; read-only public README fetch)"
GUARD = 0.30  # max allowed row-count swing per source between runs
RUN_LOG = ROOT / "state" / "run-log.json"


def fetch(url: str, offline: Path | None) -> str:
    if offline:
        return (offline / hashlib.sha1(url.encode()).hexdigest()).read_text(encoding="utf-8")
    time.sleep(1)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def parse_source(src: dict, offline: Path | None) -> list[dict]:
    rows = []
    for f in src["files"]:
        text = fetch(f["raw_url"], offline)
        if src["parser"] == "simplify":
            parsed = parse_simplify(text, f["job_type"])
        elif src["parser"] == "applyguy":
            parsed = parse_applyguy(text, f["job_type"])
        else:
            parsed = parse_speedyapply(text, f["job_type"], src["category"])
        for r in parsed:
            r["_source"] = {"source": src["name"], "source_url": src["url"]}
        rows.extend(parsed)
    return rows


def last_row_counts() -> dict:
    if not RUN_LOG.exists():
        return {}
    log = json.loads(RUN_LOG.read_text())
    entries = log.get("runs", [])
    return entries[-1].get("row_counts", {}) if entries else {}


def guard_ok(name: str, count: int, prior: dict) -> bool:
    before = prior.get(name)
    return not before or abs(count - before) / before <= GUARD


def to_record(raw: dict, today: str) -> dict:
    src = raw.pop("_source")
    return {
        "id": make_id(raw["company"], raw["title"], raw["apply_url"]),
        **raw, "sources": [src], "first_seen": today, "last_seen": today,
        "status": "open", "schema_version": SCHEMA_VERSION,
    }


def keep(rec_id: str, fraction: float) -> bool:
    return int(rec_id[:8], 16) / 0xFFFFFFFF < fraction


def merge(store: list[dict], incoming: list[dict], today: str) -> dict:
    """Merge incoming records into store in place; returns counters."""
    by_id = {r["id"]: r for r in store}
    by_company: dict[str, list[dict]] = {}
    for r in store:
        by_company.setdefault(normalize(r["company"]), []).append(r)
    stats = {"new": 0, "updated": 0, "duplicates_rejected": 0}
    for rec in incoming:
        hit = by_id.get(rec["id"]) or next(
            (c for c in by_company.get(normalize(rec["company"]), []) if is_fuzzy_match(rec, c)), None)
        if hit is None:
            store.append(rec)
            by_id[rec["id"]] = rec
            by_company.setdefault(normalize(rec["company"]), []).append(rec)
            stats["new"] += 1
            continue
        stats["duplicates_rejected"] += 1
        known = {(s["source"]) for s in hit["sources"]}
        if rec["sources"][0]["source"] not in known:
            hit["sources"].append(rec["sources"][0])
        hit["last_seen"], hit["status"] = today, "open"
        stats["updated"] += 1
    return stats


def close_missing(store: list[dict], seen_ids: set[str], live_sources: set[str], today: str) -> int:
    closed = 0
    for r in store:
        if r["status"] == "open" and r["id"] not in seen_ids and all(s["source"] in live_sources for s in r["sources"]):
            r["status"], closed = "closed", closed + 1
    return closed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=float, default=1.0)
    ap.add_argument("--offline", type=Path)
    ap.add_argument("--today", default=date.today().isoformat())
    args = ap.parse_args(argv)

    sources = yaml.safe_load((ROOT / "sources.yaml").read_text())["sources"]
    prior, counts, incoming, live = last_row_counts(), {}, [], set()
    for src in sources:
        rows = parse_source(src, args.offline)
        counts[src["name"]] = len(rows)
        if not guard_ok(src["name"], len(rows), prior):
            print(f"GUARD: {src['name']} rows {prior[src['name']]} -> {len(rows)}; skipped", file=sys.stderr)
            continue
        live.add(src["name"])
        incoming += [r for raw in rows if keep((r := to_record(dict(raw), args.today))["id"], args.sample)]

    store = load_store()
    stats = merge(store, incoming, args.today)
    stats["closed"] = close_missing(store, {r["id"] for r in incoming}, live, args.today) if args.sample >= 1 else 0
    save_store(store)
    print(json.dumps({**stats, "total": len(store), "row_counts": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
