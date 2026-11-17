from pathlib import Path

from scripts.parsers import _md_cells, _title_category, parse_applyguy, parse_simplify, parse_speedyapply, parse_vansh, parse_yt6363

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
    assert rows[2]["location"] == "Burnaby, BC, Canada; Vancouver, BC, Canada"  # new-grad README uses </br>


def test_speedyapply_rows_salary_and_linkless_rows():
    rows = parse_speedyapply((FIX / "speedyapply.md").read_text(encoding="utf-8"), "new_grad", "swe")
    assert [r["company"] for r in rows] == ["Microsoft", "Amazon"]
    assert rows[0]["salary"] == "$168k/yr" and rows[1]["salary"] is None
    assert rows[0]["job_type"] == "new_grad" and rows[0]["category"] == "swe"


def test_applyguy_original_link_and_category():
    rows = parse_applyguy((FIX / "applyguy.md").read_text(encoding="utf-8"), "internship")
    assert len(rows) == 4  # row with only the referral link is skipped
    assert all("applyguy.ai" not in r["apply_url"] for r in rows)
    assert rows[0]["company"] == "Allegion" and rows[0]["category"] == "swe"
    assert rows[0]["apply_url"].startswith("https://allegion.wd5.myworkdayjobs.com/")
    assert rows[0]["job_type"] == "internship" and rows[0]["salary"] is None
    assert rows[1]["category"] == "hardware"  # "Embedded Design Engineering Intern – Firmware"


def test_applyguy_escaped_pipe_stays_in_the_role():
    nex = parse_applyguy((FIX / "applyguy.md").read_text(encoding="utf-8"), "internship")[3]
    assert nex["company"] == "Nex" and nex["title"] == "Summer 2027 | Software Engineer Intern (Sports & Fitness)"
    assert nex["location"] == "San Jose, CA"
    assert nex["apply_url"] == nex["url"] == "https://job-boards.greenhouse.io/nex/jobs/5421056008"


def test_md_cells_split_on_unescaped_pipes_only():
    assert _md_cells(r"| Nex | Summer 2027 \| Intern | San Jose, CA |") == ["Nex", "Summer 2027 | Intern", "San Jose, CA"]
    assert _md_cells("| Acme | Finance Intern | |") == ["Acme", "Finance Intern", ""]  # empty last cell kept
    assert _md_cells("|---|---:|") == ["---", "---:"]


def test_markdown_parsers_keep_an_escaped_pipe_inside_the_role():
    role, link = r"Summer 2027 \| Software Engineer Intern", "https://jobs.example.com/1"
    speedyapply = (
        "| Company | Position | Location | Salary | Posting | Age |\n|---|---|---|---|---|---|\n"
        f'| Acme | {role} | Remote | N/A | <a href="{link}">Apply</a> | 2d |\n'
    )
    vansh = (
        "| Company | Role | Location | Application/Link | Date Posted |\n|---|---|---|---|---|\n"
        f'| Acme | {role} | Remote | <a href="{link}">Apply</a> | Nov 02 |\n'
    )
    yt6363 = (
        "## Software engineering\n\n| Company | Role | Location | Posted | Apply |\n|---|---|---|---|---|\n"
        f"| Acme | {role} | Remote | 2d | [Apply]({link}) |\n"
    )
    parsed = [
        parse_speedyapply(speedyapply, "internship", "swe"),
        parse_vansh(vansh, "internship"),
        parse_yt6363(yt6363, "internship"),
    ]
    expected = [("Acme", "Summer 2027 | Software Engineer Intern", "Remote", link)]
    assert [[(r["company"], r["title"], r["location"], r["apply_url"]) for r in rows] for rows in parsed] == [expected] * 3


def test_title_category_prefers_specific_family_over_generic_engineering_words():
    cases = {
        "Firmware Developer - Internship": "hardware",
        "Intern - Data Engineer AI (Databricks, SQL, Python)": "ai_ml_data",
        "2027 Summer Intern - AI/ML Engineer, Simulation": "ai_ml_data",
        "Cloud DevOps Internship": "swe",
        "Site Reliability Engineer Intern — Summer 2027": "swe",
        "Product Strategy Intern - Summer 2027": "pm",
        "2027 IT-Product & Strategy Summer Intern": "pm",
        "Product Operations Engineer Intern": "pm",
        "Infrastructure Engineer Intern": "swe",
        "Intern - UX/UI Front End Engineer - Starting Spring 2027": "swe",
        "Assistant Front End Manager Trainee": None,
        "Health Insurance Product Intern": None,
        "Data Analyst Intern": "ai_ml_data",
        "Data and Analytics Engineer Intern": "ai_ml_data",
        "Business Intelligence (BI) Intern": "ai_ml_data",
        "ASIC Engineer Intern": "hardware",
        "FPGA Intern": "hardware",
        "CPU Design Verification Engineer Intern": "hardware",
        "Analog IC Design Co-op": "hardware",
        "Application Development Intern": "swe",
        "Frontend Engineer Intern": "swe",
        "Design Engineer Intern, Pathfinding": "hardware",
        "Electrical & Computer Engineering Intern": "hardware",
        "Analog Mixed-Signal Modeling Software Engineer": "swe",
        "Network Site Design Intern": None,
        "Data Center Engineer Intern": None,
        "Risk & Analytics Core Intern": None,
        "Cybersecurity Intern": None,
        "Deep Learning Intern": "ai_ml_data",
        "Computer Vision Intern, Multiple Teams": "ai_ml_data",
        "Perception Intern": "ai_ml_data",
        "Software Engineer II - Perception": "swe",
        "Applied Scientist Intern, Turing": "ai_ml_data",
        "Research Scientist Intern": "ai_ml_data",
        "AI Scientist/Engineer Intern": "ai_ml_data",
        "AI Research Intern": "ai_ml_data",
        "Student Researcher Intern, Seed Model - AI Foundation Model Infrastructure": "ai_ml_data",
        "Data Governance Engineer Intern": "ai_ml_data",
    }
    assert {t: _title_category(t) for t in cases} == cases


def test_vansh_continuations_locked_rows_and_multi_location():
    rows = parse_vansh((FIX / "vansh.md").read_text(encoding="utf-8"), "internship")
    assert [r["company"] for r in rows] == ["JM Family Enterprises", "TikTok", "TikTok", "Insomniac Games", "Sierra Nevada Corporation"]  # 🔒 row skipped, ↳ inherits
    assert rows[0]["apply_url"] == "https://go.vansh.nyc/19j?s=y" and rows[0]["url"] == rows[0]["apply_url"]
    assert rows[0]["category"] is None  # "AI Intern" matches no title family
    assert rows[1]["category"] == "ai_ml_data" and rows[2]["category"] == "ai_ml_data"
    assert rows[3]["location"] == "Burbank, CA; Remote; United States"
    assert rows[4]["category"] == "hardware" and rows[4]["citizenship"] == "us_citizenship_required"
    assert all(r["job_type"] == "internship" and r["salary"] is None for r in rows)


def test_yt6363_section_categories_promo_links_and_escapes():
    rows = parse_yt6363((FIX / "yt6363.md").read_text(encoding="utf-8"), "internship")
    assert [r["category"] for r in rows] == ["pm", "pm", "ai_ml_data", "ai_ml_data", None, None, None, None, "swe", "swe"]
    assert rows[0]["company"] == "Entegris" and rows[2]["company"] == "Nexus One"  # promo link text, plain cell
    assert not any("findyourrolefirst" in r["apply_url"] + r["url"] for r in rows)
    assert rows[2]["apply_url"] == "https://jobs.ashbyhq.com/nexus-cognitive/22c64819-67fc-48d0-b206-5b41d370f6a5/application"
    assert rows[2]["url"] == rows[2]["apply_url"]
    assert rows[1]["title"] == "Program Manager Intern [Summer 2027] 🛂" and rows[9]["title"] == "Software Engineer Intern (C#)"
    assert rows[3]["location"].endswith("(+6 more)")
    assert rows[7]["location"] == "US-TX-MCKINNEY-513PW ~ 2501 W University Dr ~ PW BLDG"
    assert rows[0]["sponsorship"] is None  # 🛂 marks a likely sponsor here, not no_sponsorship
    assert all(r["job_type"] == "internship" and r["salary"] is None and r["citizenship"] is None for r in rows)


def test_yt6363_title_fallback_outside_mapped_sections_and_linkless_rows():
    text = (
        "## Business, marketing and finance\n\n| Company | Role | Location | Posted | Apply |\n|---|---|---|---|---|\n"
        "| Acme | Business Intelligence Intern | Remote | 2d | [Apply](https://jobs.example.com/1) |\n"
        "| Acme | Finance Intern | Remote | 2d | |\n"
    )
    rows = parse_yt6363(text, "internship")
    assert [(r["title"], r["category"]) for r in rows] == [("Business Intelligence Intern", "ai_ml_data")]
