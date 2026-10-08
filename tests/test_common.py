from scripts.common import canonical_url, is_fuzzy_match, make_id, normalize


def test_normalize_strips_emoji_punctuation_and_legal_suffix():
    assert normalize("Acme, Inc.") == "acme"
    assert normalize("Software Engineer Intern 🛂 (2027)") == "software engineer intern 2027"


def test_canonical_url_drops_tracking_fragment_and_slash():
    a = "https://Jobs.Example.com/x/?utm_source=Simplify&ref=Simplify&gh_jid=5#top"
    assert canonical_url(a) == "https://jobs.example.com/x?gh_jid=5"


def test_id_ignores_tracking_and_case():
    a = make_id("Acme Inc.", "SWE Intern", "https://a.com/j/1?utm_source=x")
    b = make_id("acme", "swe intern", "https://A.com/j/1/")
    assert a == b and len(a) == 16


def test_fuzzy_match_requires_company_type_title_and_location():
    base = {"company": "Acme", "title": "Software Engineer Intern", "location": "New York, NY", "job_type": "internship"}
    near = {**base, "title": "Software Engineer Intern.", "location": "NYC; New York"}
    assert is_fuzzy_match(base, near)
    assert not is_fuzzy_match(base, {**near, "job_type": "new_grad"})
    assert not is_fuzzy_match(base, {**near, "title": "Data Scientist Intern"})
    assert not is_fuzzy_match(base, {**near, "location": "Austin, TX"})


def test_fuzzy_match_is_symmetric():
    # SequenceMatcher.ratio() scores this pair 0.907 one way and 0.889 the other.
    a = {"company": "C-Serv", "title": "F5 BIG-IP - F5 Distributed Cloud - XC Consultant - Indonesia",
         "location": "", "job_type": "new_grad"}
    b = {**a, "title": "F5 BIG-IP - F5 Distributed Cloud - XC Consultant - Singapore",
         "location": "Singapore, Singapore"}
    assert is_fuzzy_match(a, b) == is_fuzzy_match(b, a)
    assert not is_fuzzy_match(a, b)
