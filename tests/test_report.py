from scripts import report
from scripts.common import canonical_url, make_id


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
    assert summary == {"groups": 2, "records": 4, "cross_source": 1, "mixed_spelling": 0, "same_company": 1,
                       "company_prefix": 0, "different_company": 1, "would_merge": 1, "below_threshold": 0}
    text = report.render(groups, summary, "2026-11-01")
    assert "SWE Intern \\| Summer" in text
    assert "as of 2026-11-01" in text
    assert text == report.render(*report.build(list(reversed(store))), "2026-11-01")


# One Workday req (R8002) as three feeds publish it; the ids are the ones the store holds (#132).
CSAA = "https://aaaie.wd1.myworkdayjobs.com/{}/job/Arizona---Home-Teleworkers/Data-Science-Intern_R8002"
LOCALE = CSAA.format("en-US/csaacareers2")  # speedyapply
CASE = CSAA.format("CSAACareers2") + "?utm_source=Simplify&ref=Simplify"  # SimplifyJobs
PLAIN = CSAA.format("csaacareers2")  # yt6363


def csaa_records():
    return [
        rec("e36057269c632a63", "CSAA Insurance Group", "Data Science Intern", LOCALE, source="speedyapply-2027-ai"),
        rec("db07d37a29e31149", "CSAA Insurance Group", "Data Science Intern", CASE, source="simplify-summer2027-internships"),
        rec("0fc2b28ab181ba8d", "Aaaie", "Data Science Intern", PLAIN, source="yt6363-summer-2027-internships"),
    ]


def test_group_key_folds_workday_locale_and_path_case():
    key = report.group_key(PLAIN)
    assert key == PLAIN.lower()
    assert report.group_key(LOCALE) == key  # locale segment only
    assert report.group_key(CASE) == key  # path case only
    assert report.group_key(CSAA.format("en-US/CSAACareers2")) == key  # both
    assert report.group_key(CSAA.format("en-us/csaacareers2")) == key  # lowercase locale
    # Only one leading segment goes, and the query keeps its case.
    assert (report.group_key("https://x.wd5.myworkdayjobs.com/fr-CA/en-US/Site/job/A_R1?jobReq=R1")
            == "https://x.wd5.myworkdayjobs.com/en-us/site/job/a_r1?jobReq=R1")


def test_workday_spellings_share_a_group_and_keep_their_ids():
    store = csaa_records()
    groups = report.shared_url_groups(store)
    assert list(groups) == [report.group_key(PLAIN)]
    assert {r["id"] for r in groups[report.group_key(PLAIN)]} == {r["id"] for r in store}
    assert report.would_merge(store[0], store[1])
    # canonical_url and make_id are unchanged: each spelling keeps its own canonical form and stored id.
    assert canonical_url(LOCALE) == LOCALE
    assert canonical_url(CASE) == CSAA.format("CSAACareers2")
    for r in store:
        assert make_id(r["company"], r["title"], r["apply_url"]) == r["id"]


def test_other_hosts_keep_canonical_url():
    lever = "https://jobs.lever.co/acme/A1b2C3d4"
    assert report.group_key(lever) == canonical_url(lever)
    assert report.group_key("https://careers.acme.com/en-US/Job/1") == "https://careers.acme.com/en-US/Job/1"
    store = [rec("l1", "Acme", "SWE Intern", lever), rec("l2", "Acme", "SWE Intern", lever.lower())]
    assert report.shared_url_groups(store) == {}
    assert not report.would_merge(*store)


def test_render_shows_each_spelling_when_a_group_mixes_them():
    store = csaa_records() + [rec("a1", "Acme", "SWE Intern", "https://a.com/1"),
                              rec("a2", "Acme", "SWE Intern - Summer", "https://a.com/1/?utm_source=x")]
    groups, summary = report.build(store)
    assert (summary["groups"], summary["mixed_spelling"]) == (2, 1)
    text = report.render(groups, summary, "2026-11-16")
    for url in (LOCALE, CSAA.format("CSAACareers2"), PLAIN):
        assert text.count(f"<{url}>") == 1
    assert text.count("<https://a.com/1>") == 1  # one spelling: shown once, on the group's first row
