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
    # speedyapply country spellings for cities SimplifyJobs writes with a region code or bare.
    "london, united kingdom": "London, UK", "singapore, singapore": "Singapore",
    "toronto, canada": "Toronto, ON, Canada", "vancouver, canada": "Vancouver, BC, Canada",
    "usa": "United States",
}
_REMOTE_IN = re.compile(r"^remote in (.+)$", re.I)
# speedyapply writes country-level and state-level US cells with a `USA` suffix ("USA",
# "Iowa, USA"); SimplifyJobs writes "United States" and the bare state name.
_STATE_USA = re.compile(r"^(.+), usa$")
_US_STATES = {s.lower(): s for s in (
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
    "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
)}
# Tokens too generic to count as a location overlap: "city" (New York City vs Salt Lake
# City) and two-letter state or country codes (Irvine, CA vs Los Angeles, CA).
_LOCATION_STOP = {"city"}

# Language and platform names that make two otherwise near-identical titles different roles
# (Jump Trading lists "Campus C++ Software Engineer - Intern" and "Campus Python Software
# Engineer - Intern" with separate apply links; SequenceMatcher scores them 0.901). Symbols
# are rewritten before `normalize` strips punctuation, so "C++" and "C" stay distinct.
_TECH_SPELLINGS = {"c++": "cpp", "c#": "csharp", ".net": "dotnet", "node.js": "nodejs", "objective-c": "objectivec"}
_TECH_TOKENS = {
    "c", "cpp", "csharp", "dotnet", "python", "java", "javascript", "typescript", "nodejs", "go", "golang",
    "rust", "kotlin", "swift", "scala", "ruby", "php", "objectivec", "ios", "android", "react", "angular",
}


def normalize(text: str) -> str:
    """Lowercase, strip emoji/punctuation, collapse whitespace, drop legal suffixes."""
    t = (text or "").lower().replace("&amp;", "&")
    t = _EMOJI_AND_PUNCT.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return _LEGAL_SUFFIX.sub("", t).strip()


def normalize_location(location: str) -> str:
    """Collapse city, country, state and remote aliases per `;` segment; drop empty and repeated segments."""
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
        elif (m := _STATE_USA.match(seg.lower())) and m.group(1) in _US_STATES:
            seg = _US_STATES[m.group(1)]
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


def _tech_tokens(title: str) -> set[str]:
    t = (title or "").lower()
    for spelling, token in _TECH_SPELLINGS.items():
        t = t.replace(spelling, f" {token} ")
    return set(normalize(t).split()) & _TECH_TOKENS


def _loc_tokens(location: str) -> set[str]:
    return {t for t in normalize(normalize_location(location)).split() if len(t) > 2 and t not in _LOCATION_STOP}


def is_fuzzy_match(a: dict, b: dict, threshold: float = 0.9) -> bool:
    """Same company + job type, near-identical title, same language tokens, overlapping location."""
    if normalize(a["company"]) != normalize(b["company"]) or a["job_type"] != b["job_type"]:
        return False
    if _tech_tokens(a["title"]) != _tech_tokens(b["title"]):
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
