"""Validate data/jobs.jsonl. Exit 1 on duplicate ids, fuzzy duplicates, or schema violations."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .common import REQUIRED_FIELDS, SCHEMA_VERSION, STATUSES, STORE, is_fuzzy_match, make_id, normalize


def validate(path: Path = STORE) -> list[str]:
    errors, seen, by_company = [], {}, {}
    if not path.exists():
        return [f"{path} missing"]
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {n}: unparseable JSON ({exc})")
            continue
        missing = [f for f in REQUIRED_FIELDS if f not in rec]
        if missing:
            errors.append(f"line {n}: missing fields {missing}")
            continue
        if rec["status"] not in STATUSES:
            errors.append(f"line {n}: bad status {rec['status']!r}")
        if rec["schema_version"] != SCHEMA_VERSION:
            errors.append(f"line {n}: schema_version {rec['schema_version']} != {SCHEMA_VERSION}")
        if not rec["sources"]:
            errors.append(f"line {n}: empty sources[]")
        if not rec["apply_url"].startswith("http"):
            errors.append(f"line {n}: apply_url not http(s)")
        if rec["id"] != make_id(rec["company"], rec["title"], rec["apply_url"]):
            errors.append(f"line {n}: id does not match content hash")
        if rec["id"] in seen:
            errors.append(f"line {n}: duplicate id {rec['id']} (first at line {seen[rec['id']]})")
        seen[rec["id"]] = n
        by_company.setdefault(normalize(rec["company"]), []).append((n, rec))
    for group in by_company.values():
        for i, (na, a) in enumerate(group):
            for nb, b in group[i + 1:]:
                if is_fuzzy_match(a, b):
                    errors.append(f"lines {na},{nb}: fuzzy duplicate {a['company']} / {a['title']!r}")
    return errors


def main() -> int:
    errors = validate()
    for e in errors[:50]:
        print(e, file=sys.stderr)
    if errors:
        print(f"{len(errors)} error(s)", file=sys.stderr)
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
