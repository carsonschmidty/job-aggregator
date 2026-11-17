"""Report open records that share an apply URL under different ids (#68).

Usage:
    python -m scripts.report               # write docs/shared-apply-urls.md, print a JSON summary
    python -m scripts.report --out PATH    # write the report somewhere else

Fuzzy match never compares apply URLs, so one posting listed by two feeds with a title gap or
a different company spelling stays two records. This report lists those groups without
changing the store, and counts how many a URL-based merge tier (option 1 in #68) would fold.

Records group by `group_key`: `canonical_url`, except that on *.myworkdayjobs.com hosts one
leading locale segment (/en-US/) is dropped and the path is lowercased, because Workday serves
one posting under all of those spellings and feeds disagree on them (#132). Grouping,
`would_merge` and the summary counts all use that key. It is report-only: `canonical_url`, and so
`make_id` and every stored id, are unchanged.
"""
from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .common import ROOT, canonical_url, load_store, normalize

OUT = ROOT / "docs" / "shared-apply-urls.md"
CLASSES = ("same_company", "company_prefix", "different_company")
MERGE_THRESHOLD = 0.6  # title similarity proposed for option 1 in #68
# One leading /<ll>-<CC> locale segment, matched without case since the key lowercases the path
# anyway; some feeds write /en-us/.
_WORKDAY_LOCALE = re.compile(r"^/[a-z]{2}-[a-z]{2}(?=/|$)", re.I)


def group_key(url: str) -> str:
    """The URL the report groups by: `canonical_url`, with Workday's locale and path-case spellings folded.

    Only *.myworkdayjobs.com is folded: only Workday was measured (#132), and other ATS paths can
    carry case-sensitive ids. The query is left as `canonical_url` gives it.
    """
    canon = canonical_url(url)
    parts = urlsplit(canon)
    if not (parts.hostname or "").endswith(".myworkdayjobs.com"):
        return canon
    return urlunsplit(parts._replace(path=_WORKDAY_LOCALE.sub("", parts.path, count=1).lower()))


def shared_url_groups(store: list[dict]) -> dict[str, list[dict]]:
    """Open records by `group_key` of the apply URL, keeping keys with two or more distinct ids."""
    by_url: dict[str, dict[str, dict]] = {}
    for rec in store:
        if rec["status"] == "open":
            by_url.setdefault(group_key(rec["apply_url"]), {}).setdefault(rec["id"], rec)
    return {
        url: sorted(recs.values(), key=lambda r: (normalize(r["company"]), normalize(r["title"]), r["id"]))
        for url, recs in by_url.items() if len(recs) > 1
    }


def company_relation(a: str, b: str) -> str:
    """'same', 'prefix' when one normalized name is the other plus more words, else 'different'."""
    ca, cb = normalize(a), normalize(b)
    if ca == cb:
        return "same"
    # Whole words only, so "aqr" / "aqr capital management" relate but "meta" / "metabase" do not.
    if ca.startswith(cb + " ") or cb.startswith(ca + " "):
        return "prefix"
    return "different"


def classify(group: list[dict]) -> str:
    relations = {company_relation(a["company"], b["company"]) for a, b in combinations(group, 2)}
    if relations == {"same"}:
        return "same_company"
    return "company_prefix" if "different" not in relations else "different_company"


def title_similarity(a: str, b: str) -> float:
    """The measure is_fuzzy_match uses: normalized titles, lower ratio of the two directions."""
    ta, tb = normalize(a), normalize(b)
    return min(SequenceMatcher(None, ta, tb).ratio(), SequenceMatcher(None, tb, ta).ratio())


def would_merge(a: dict, b: dict, threshold: float = MERGE_THRESHOLD) -> bool:
    """Option 1 of #68 without its job-family token clause: same URL key, related company, close title."""
    if group_key(a["apply_url"]) != group_key(b["apply_url"]):
        return False
    if company_relation(a["company"], b["company"]) == "different":
        return False
    return title_similarity(a["title"], b["title"]) >= threshold


def build(store: list[dict]) -> tuple[list[dict], dict]:
    """Return (groups sorted by class then URL key, summary counts)."""
    groups = []
    for url, recs in shared_url_groups(store).items():
        related = [(a, b) for a, b in combinations(recs, 2) if company_relation(a["company"], b["company"]) != "different"]
        urls = [canonical_url(r["apply_url"]) for r in recs]
        groups.append({
            "url": url,
            "urls": urls,  # each record's own spelling, in record order
            "mixed": len(set(urls)) > 1,
            "class": classify(recs),
            "records": recs,
            "sims": [title_similarity(a["title"], b["title"]) for a, b in related],
            "merge": any(would_merge(a, b) for a, b in related),
            "cross_source": len({s["source"] for r in recs for s in r["sources"]}) > 1,
        })
    groups.sort(key=lambda g: (CLASSES.index(g["class"]), g["url"]))
    summary = {
        "groups": len(groups),
        "records": sum(len(g["records"]) for g in groups),
        "cross_source": sum(g["cross_source"] for g in groups),
        "mixed_spelling": sum(g["mixed"] for g in groups),
        **{c: sum(g["class"] == c for g in groups) for c in CLASSES},
        "would_merge": sum(g["merge"] for g in groups),
        "below_threshold": sum(bool(g["sims"]) and not g["merge"] for g in groups),
    }
    return groups, summary


def _cell(text) -> str:
    return " ".join(str(text or "").split()).replace("|", "\\|")


def render(groups: list[dict], summary: dict, as_of: str) -> str:
    t = MERGE_THRESHOLD
    lines = [
        "# Open listings that share an apply URL",
        "",
        f"Generated by `python -m scripts.report` from `data/jobs.jsonl` as of {as_of or 'n/a'} (latest `last_seen`);"
        " do not edit by hand. The report does not change the store (option 2 of #68).",
        "",
        "Each group is a set of open records whose `apply_url` gives the same URL key but whose ids differ."
        " The key is `canonical_url`, except on `*.myworkdayjobs.com` hosts, where one leading locale segment"
        " (`/en-US/`) is dropped and the path is lowercased: Workday serves one posting under each of those"
        " spellings, and feeds disagree on them (#132). Other hosts keep `canonical_url`, since their paths can"
        " carry case-sensitive ids. The counts and option 1 below use the same key. It exists only in this report;"
        " `canonical_url` and record ids are unchanged. Fuzzy match never compares apply URLs, so these stay"
        " separate records.",
        "",
        "| | Count |",
        "|---|---:|",
        f"| Groups | {summary['groups']} |",
        f"| Records in groups | {summary['records']} |",
        f"| Cross-source groups | {summary['cross_source']} |",
        f"| Groups whose records spell the URL differently | {summary['mixed_spelling']} |",
        *(f"| `{c}` groups | {summary[c]} |" for c in CLASSES),
        f"| Groups option 1 would merge at title similarity {t} | {summary['would_merge']} |",
        f"| Groups with a same or prefix company pair below {t} | {summary['below_threshold']} |",
        "",
        "- `same_company`: every record has the same `normalize(company)`. `company_prefix`: the names differ,"
        " but in every pair one equals the other or is the other followed by more words (`aqr` / `aqr capital"
        " management`). `different_company`: anything else, such as a parent and a subsidiary or a spelling"
        " `normalize` does not join.",
        "- Cross-source: the records' `sources[]` together name two or more sources.",
        "- `Apply URL` is the `canonical_url` of the records' `apply_url`, on a group's first row. When the records"
        " spell it differently (a Workday locale segment or path case), every row shows its own record's"
        " `canonical_url` instead; `Option 1` and `Sim` still fill only a group's first row.",
        f"- Option 1: a group counts when at least one pair of its records has a same or prefix company and a"
        f" title similarity of {t} or more, measured as `is_fuzzy_match` does (`SequenceMatcher` on `normalize`d"
        " titles, lower ratio of the two directions). The job-family token clause is not counted; it could add at"
        " most the groups in the last row. Job type, language tokens, the term, year and degree-level guard (#123)"
        " and location, which `is_fuzzy_match` also checks, are not part of the rule.",
        "- `Sim` lists the title similarity of each same or prefix company pair in the group; `-` when there is none.",
    ]
    for cls in CLASSES:
        members = [g for g in groups if g["class"] == cls]
        lines += ["", f"## {cls} ({len(members)})", ""]
        if not members:
            lines.append("None.")
            continue
        lines += [
            "| Apply URL | Option 1 | Sim | id | Company | Title | Location | Sources |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for g in members:
            stats = ["merge" if g["merge"] else "apart", ", ".join(f"{s:.3f}" for s in g["sims"]) or "-"]
            for i, (r, url) in enumerate(zip(g["records"], g["urls"])):
                sources = ", ".join(s["source"] for s in r["sources"])
                link = f"<{_cell(url)}>" if i == 0 or g["mixed"] else ""
                row = [link] + (stats if i == 0 else ["", ""]) + [
                    f"`{r['id']}`", _cell(r["company"]), _cell(r["title"]), _cell(r["location"]), _cell(sources)]
                lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    store = load_store()
    groups, summary = build(store)
    # Date the report by the data, not the clock, so a rerun on an unchanged store is a no-op.
    as_of = max((r["last_seen"] for r in store), default="")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(groups, summary, as_of))
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
