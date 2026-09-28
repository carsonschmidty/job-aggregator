from pathlib import Path

from scripts.parsers import parse_simplify, parse_speedyapply

FIX = Path(__file__).parent / "fixtures"


def test_simplify_rows_categories_and_continuations():
    rows = parse_simplify((FIX / "simplify.html").read_text(encoding="utf-8"), "internship")
    assert [r["company"] for r in rows] == ["Waymo", "Waymo", "Acme Inc."]  # closed row skipped, ↳ inherits
    assert [r["category"] for r in rows] == ["swe", "swe", "pm"]
    assert rows[0]["apply_url"].startswith("https://careers.withwaymo.com/jobs?gh_jid=1")
    assert rows[0]["url"] == "https://simplify.jobs/p/abc"
    assert rows[0]["sponsorship"] == "no_sponsorship" and rows[0]["citizenship"] is None
    assert rows[1]["citizenship"] == "us_citizenship_required"
    assert rows[1]["location"] == "Tempe, AZ; Dallas, TX"


def test_speedyapply_rows_salary_and_linkless_rows():
    rows = parse_speedyapply((FIX / "speedyapply.md").read_text(encoding="utf-8"), "new_grad", "swe")
    assert [r["company"] for r in rows] == ["Microsoft", "Amazon"]
    assert rows[0]["salary"] == "$168k/yr" and rows[1]["salary"] is None
    assert rows[0]["job_type"] == "new_grad" and rows[0]["category"] == "swe"
