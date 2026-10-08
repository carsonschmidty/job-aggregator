"""Shared helpers: normalization, canonical URLs, ids, fuzzy matching, store IO."""
from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "jobs.jsonl"

REQUIRED_FIELDS = (
    "id", "company", "title", "location", "url", "apply_url", "sources",
    "category", "job_type", "first_seen", "last_seen", "status",
    "sponsorship", "citizenship", "salary", "schema_version",
)
STATUSES = ("open", "closed")

_LEGAL_SUFFIX = re.compile(r"\b(inc|llc|ltd|corp|corporation|co|company|plc|gmbh)\b\.?$")
_TRACKING = re.compile(r"^(utm_.*|ref|source|gh_src|embed|fbclid|gclid|lever-source.*|src)$", re.I)
_EMOJI_AND_PUNCT = re.compile(r"[^a-z0-9 ]+")


def normalize(text: str) -> str:
    """Lowercase, strip emoji/punctuation, collapse whitespace, drop legal suffixes."""
    t = (text or "").lower().replace("&amp;", "&")
    t = _EMOJI_AND_PUNCT.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return _LEGAL_SUFFIX.sub("", t).strip()


def canonical_url(url: str) -> str:
    """Lowercase host, drop tracking params, fragment and trailing slash."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING.match(k)]
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), ""))


def make_id(company: str, title: str, apply_url: str) -> str:
    key = f"{normalize(company)}|{normalize(title)}|{canonical_url(apply_url)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _loc_tokens(location: str) -> set[str]:
    return {t for t in normalize(location).split() if len(t) > 1}


def is_fuzzy_match(a: dict, b: dict, threshold: float = 0.9) -> bool:
    """Same company + job type, near-identical title, overlapping location."""
    if normalize(a["company"]) != normalize(b["company"]) or a["job_type"] != b["job_type"]:
        return False
    ta, tb = normalize(a["title"]), normalize(b["title"])
    # SequenceMatcher.ratio() is not symmetric; require the threshold in both
    # directions so ingest (incoming, existing) and validate (existing, incoming) agree.
    if min(SequenceMatcher(None, ta, tb).ratio(), SequenceMatcher(None, tb, ta).ratio()) < threshold:
        return False
    la, lb = _loc_tokens(a["location"]), _loc_tokens(b["location"])
    return not la or not lb or bool(la & lb)


def load_store(path: Path = STORE) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def save_store(records: list[dict], path: Path = STORE) -> None:
    records = sorted(records, key=lambda r: (normalize(r["company"]), normalize(r["title"]), r["id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
