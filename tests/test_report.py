from scripts import report


def rec(id_, company, title, url, status="open", source="s1", location="New York, NY"):
    return {"id": id_, "company": company, "title": title, "location": location, "apply_url": url,
            "status": status, "sources": [{"source": source, "source_url": "https://x"}]}


def test_groups_keep_open_records_with_distinct_ids_per_canonical_url():
    store = [
        rec("a1", "Acme", "SWE Intern", "https://a.com/1?utm_source=x"),
        rec("a2", "Acme", "Software Engineer Intern", "https://A.com/1/", source="s2"),
        rec("a3", "Acme", "Data Intern", "https://a.com/1", status="closed"),  # closed: left out
        rec("b1", "Beta", "SWE Intern", "https://b.com/1"),  # only record behind its URL
        rec("c1", "Gamma", "SWE Intern", "https://c.com/1"),
        rec("c1", "Gamma", "SWE Intern", "https://c.com/1", source="s2"),  # same id twice is one listing
    ]
    groups = report.shared_url_groups(store)
    assert list(groups) == ["https://a.com/1"]
    assert {r["id"] for r in groups["https://a.com/1"]} == {"a1", "a2"}


def test_classify_by_company_relation():
    url = "https://a.com/1"
    same = [rec("1", "Acme Inc.", "Quantitative Investment Intern", url),
            rec("2", "Acme", "Quantitative Investment Internship Program - Summer 2027", url)]
    prefix = [rec("1", "Akuna Capital", "Trading Intern", url), rec("2", "Akuna Capital University", "Trading Intern", url)]
    different = [rec("1", "IDeaS", "Data Science Intern", url), rec("2", "SAS", "Data Science Intern", url)]
    assert report.classify(same) == "same_company"
    assert report.classify(prefix) == "company_prefix"
    assert report.classify(different) == "different_company"
    # A prefix must end on a word boundary.
    assert report.company_relation("Meta", "Metabase") == "different"


def test_would_merge_follows_option_one():
    url = "https://a.com/1"
    a = rec("1", "Acme", "Quantitative Investment Intern", url)
    assert report.would_merge(a, rec("2", "Acme", "Quantitative Investment Internship Program - Summer 2027", url))
    assert report.would_merge(rec("1", "AQR", "Research Intern", url), rec("2", "AQR Capital Management", "Research Intern", url))
    assert not report.would_merge(rec("1", "IDeaS", "Data Science Intern", url), rec("2", "SAS", "Data Science Intern", url))
    assert not report.would_merge(a, rec("2", "Acme", "Quantitative Investment Intern", "https://a.com/2"))


def test_would_merge_keeps_distinct_junior_roles_apart():
    url = "https://bulls-media.com/career/sendcv"
    designer = rec("1", "Bulls Media", "Junior Graphic Designer", url)
    sales = rec("2", "Bulls Media", "Junior Sales Representative", url)
    assert report.title_similarity(designer["title"], sales["title"]) < report.MERGE_THRESHOLD
    assert not report.would_merge(designer, sales)
    # The developer roles Bulls Media lists behind this page score 0.784, so 0.6 alone folds them (#68).
    backend = rec("3", "Bulls Media", "Junior + Backend Developer", url)
    fullstack = rec("4", "Bulls Media", "Junior+ Full Stack Developer", url)
    assert report.would_merge(backend, fullstack)


def test_build_counts_and_render_escapes_pipes():
    store = [
        rec("a1", "Acme", "SWE Intern", "https://a.com/1"),
        rec("a2", "Acme", "SWE Intern | Summer", "https://a.com/1", source="s2"),
        rec("i1", "IDeaS", "Data Intern", "https://s.com/1"),
        rec("i2", "SAS", "Data Intern", "https://s.com/1"),
    ]
    groups, summary = report.build(store)
    assert [g["class"] for g in groups] == ["same_company", "different_company"]
    assert summary == {"groups": 2, "records": 4, "cross_source": 1, "same_company": 1, "company_prefix": 0,
                       "different_company": 1, "would_merge": 1, "below_threshold": 0}
    text = report.render(groups, summary, "2026-11-01")
    assert "SWE Intern \\| Summer" in text
    assert "as of 2026-11-01" in text
    assert text == report.render(*report.build(list(reversed(store))), "2026-11-01")
