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

# Short forms used by the speedyapply tables, mapped to the `City, ST` form SimplifyJobs
# publishes. Keys are compared after lowercasing and whitespace collapse, per `;` segment.
_LOCATION_ALIAS = {
    "nyc": "New York City, NY", "nyc, ny": "New York City, NY", "new york": "New York City, NY",
    "new york, ny": "New York City, NY", "new york city": "New York City, NY",
    "sf": "San Francisco, CA", "san francisco": "San Francisco, CA",
    "la": "Los Angeles, CA", "los angeles": "Los Angeles, CA",
    "remote - usa": "Remote - USA", "remote in usa": "Remote - USA", "remote, u.s.": "Remote - USA",
    "remote - us": "Remote - USA", "remote usa": "Remote - USA", "remote (usa)": "Remote - USA",
}
_REMOTE_IN = re.compile(r"^remote in (.+)$", re.I)
# Tokens too generic to count as a location overlap: "city" (New York City vs Salt Lake
# City) and two-letter state or country codes (Irvine, CA vs Los Angeles, CA).
_LOCATION_STOP = {"city"}


def normalize(text: str) -> str:
    """Lowercase, strip emoji/punctuation, collapse whitespace, drop legal suffixes."""
    t = (text or "").lower().replace("&amp;", "&")
    t = _EMOJI_AND_PUNCT.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return _LEGAL_SUFFIX.sub("", t).strip()


def normalize_location(location: str) -> str:
    """Collapse city and remote aliases per `;` segment; drop empty and repeated segments."""
    out: list[str] = []
    for segment in (location or "").split(";"):
        seg = re.sub(r"\s+", " ", segment).strip()
        if not seg:
            continue
        alias = _LOCATION_ALIAS.get(seg.lower())
        if alias:
            seg = alias
        elif (m := _REMOTE_IN.match(seg)):
            seg = f"Remote - {m.group(1)}"
        if seg not in out:
            out.append(seg)
    return "; ".join(out)


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
    return {t for t in normalize(normalize_location(location)).split() if len(t) > 2 and t not in _LOCATION_STOP}


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
