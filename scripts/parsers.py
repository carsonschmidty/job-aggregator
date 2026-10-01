"""Parsers for the seed sources. Each returns a list of raw listing dicts."""
from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>")
_HREF = re.compile(r'href="([^"]+)"')
_SIMPLIFY_HEADING = re.compile(r"^## .*?(Software Engineering|Product Management|Data Science|Quantitative|Hardware)", re.M)
_CATEGORY = {
    "Software Engineering": "swe", "Product Management": "pm",
    "Data Science": "ai_ml_data", "Quantitative": "quant", "Hardware": "hardware",
}


def _text(fragment: str) -> str:
    fragment = re.sub(r"<summary>.*?</summary>", "", fragment, flags=re.S)
    fragment = re.sub(r"<br\s*/?>", "; ", fragment)
    return html.unescape(_TAG.sub("", fragment)).strip()


def _flags(title: str) -> dict:
    return {
        "sponsorship": "no_sponsorship" if "🛂" in title else None,
        "citizenship": "us_citizenship_required" if "🇺🇸" in title else None,
    }


def _clean_url(url: str) -> str:
    return html.unescape(url).strip()


def parse_simplify(text: str, job_type: str) -> list[dict]:
    """SimplifyJobs READMEs: HTML tables under '## <category>' headings."""
    headings = [(m.start(), _CATEGORY[m.group(1)]) for m in _SIMPLIFY_HEADING.finditer(text)]
    rows, company = [], ""
    for m in re.finditer(r"<tr>(.*?)</tr>", text, re.S):
        cells = re.findall(r"<td>(.*?)</td>", m.group(1), re.S)
        if len(cells) < 5:
            continue
        cat = next((c for pos, c in reversed(headings) if pos < m.start()), "swe")
        name = _text(cells[0])
        if name and name != "↳":
            company = name.lstrip("🔥 ").strip()
        title = _text(cells[1])
        hrefs = [_clean_url(h) for h in _HREF.findall(cells[3])]
        if not hrefs or not title:
            continue  # closed (🔒) or malformed row
        apply_url = next((h for h in hrefs if "simplify.jobs" not in h), hrefs[0])
        detail = next((h for h in hrefs if "simplify.jobs/p/" in h), apply_url)
        rows.append({
            "company": company, "title": title, "location": _text(cells[2]),
            "apply_url": apply_url, "url": detail, "category": cat,
            "job_type": job_type, "salary": None, **_flags(title),
        })
    return rows


def parse_speedyapply(text: str, job_type: str, category: str) -> list[dict]:
    """speedyapply READMEs: markdown tables with a header row naming the columns."""
    rows, cols = [], None
    for line in text.splitlines():
        if not line.startswith("|"):
            cols = None if line.strip() else cols
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "Company":
            cols = [c.lower() for c in cells]
            continue
        if cols is None or set(line.replace("|", "").strip()) <= {"-", " ", ":"}:
            continue
        rec = dict(zip(cols, cells))
        hrefs = [_clean_url(h) for h in _HREF.findall(rec.get("posting", ""))]
        title = _text(rec.get("position", ""))
        if not hrefs or not title:
            continue
        salary = _text(rec.get("salary", "")) or None
        rows.append({
            "company": _text(rec.get("company", "")), "title": title,
            "location": _text(rec.get("location", "")), "apply_url": hrefs[0],
            "url": hrefs[0], "category": category, "job_type": job_type,
            "salary": None if salary in (None, "N/A", "-") else salary, **_flags(title),
        })
    return rows


_MD_LINK = re.compile(r"\]\((https?://[^)\s]+)\)")
_TITLE_CATEGORY = (
    ("quant", "quant"), ("product manag", "pm"), ("machine learning", "ai_ml_data"),
    ("data scien", "ai_ml_data"), ("hardware", "hardware"), ("software", "swe"),
)


def _title_category(title: str) -> str | None:
    low = title.lower()
    return next((cat for needle, cat in _TITLE_CATEGORY if needle in low), None)


def parse_applyguy(text: str, job_type: str) -> list[dict]:
    """ApplyGuy READMEs: markdown tables whose Actions cell ends with the original listing link."""
    rows, cols = [], None
    for line in text.splitlines():
        if not line.startswith("|"):
            cols = None if line.strip() else cols
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "Company":
            cols = [c.lower() for c in cells]
            continue
        if cols is None or set(line.replace("|", "").strip()) <= {"-", " ", ":"}:
            continue
        rec = dict(zip(cols, cells))
        links = _MD_LINK.findall(rec.get("actions", ""))
        title = _text(rec.get("role", ""))
        if len(links) < 2 or not title:
            continue  # first link is the applyguy.ai referral; the second is the original posting
        rows.append({
            "company": _text(rec.get("company", "")), "title": title,
            "location": _text(rec.get("location", "")), "apply_url": links[-1],
            "url": links[-1], "category": _title_category(title), "job_type": job_type,
            "salary": None, **_flags(title),
        })
    return rows


PARSERS = {"simplify": parse_simplify, "speedyapply": parse_speedyapply, "applyguy": parse_applyguy}
