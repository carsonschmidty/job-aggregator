from pathlib import Path

from scripts.parsers import _title_category, parse_applyguy, parse_simplify, parse_speedyapply

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


def test_applyguy_original_link_and_category():
    rows = parse_applyguy((FIX / "applyguy.md").read_text(encoding="utf-8"), "internship")
    assert len(rows) == 3  # row with only the referral link is skipped
    assert all("applyguy.ai" not in r["apply_url"] for r in rows)
    assert rows[0]["company"] == "Allegion" and rows[0]["category"] == "swe"
    assert rows[0]["apply_url"].startswith("https://allegion.wd5.myworkdayjobs.com/")
    assert rows[0]["job_type"] == "internship" and rows[0]["salary"] is None
    assert rows[1]["category"] == "hardware"  # "Embedded Design Engineering Intern – Firmware"


def test_title_category_prefers_specific_family_over_generic_engineering_words():
    cases = {
        "Firmware Developer - Internship": "hardware",
        "Intern - Data Engineer AI (Databricks, SQL, Python)": "ai_ml_data",
        "2027 Summer Intern - AI/ML Engineer, Simulation": "ai_ml_data",
        "Cloud DevOps Internship": "swe",
        "Site Reliability Engineer Intern — Summer 2027": "swe",
        "Product Strategy Intern - Summer 2027": "pm",
        "Health Insurance Product Intern": None,
    }
    assert {t: _title_category(t) for t in cases} == cases
