from scripts.common import canonical_url, is_fuzzy_match, make_id, normalize, normalize_location


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


def test_fuzzy_match_keeps_language_variants_apart():
    # Ratio is 0.901, above the threshold, but these are two roles with two apply links (#40).
    a = {"company": "Jump Trading", "title": "Campus C++ Software Engineer - Intern",
         "location": "Hong Kong +1", "job_type": "internship"}
    b = {**a, "title": "Campus Python Software Engineer - Intern"}
    assert not is_fuzzy_match(a, b)
    assert not is_fuzzy_match(a, {**a, "title": "Campus C Software Engineer - Intern"})
    assert is_fuzzy_match(a, {**a, "title": "Campus C++ Software Engineer Intern"})


def test_fuzzy_match_still_accepts_true_variants():
    base = {"company": "Acme", "location": "Austin, TX", "job_type": "new_grad"}
    pairs = [
        ("Software Engineer Intern", "Software Engineering Intern"),
        ("Data Engineer 1", "Data Engineer I"),
        ("Software Engineer \u2013 University Graduate", "Software Engineer - University Graduate - US"),
    ]
    for x, y in pairs:
        assert is_fuzzy_match({**base, "title": x}, {**base, "title": y}), (x, y)


def test_fuzzy_match_keeps_term_year_and_degree_variants_apart():
    # Each pair scores at least 0.9, but the titles name two postings with two ATS job ids
    # (Skydio, Amazon, Google, Capital One; #123). Dotted degrees read like undotted ones.
    base = {"company": "Acme", "location": "Santa Clara, CA", "job_type": "internship"}
    pairs = [
        ("Embedded Software Engineer Intern - Summer 2027", "Embedded Software Engineer Intern - Winter 2027"),
        ("Software Development Engineer - 2026", "Software Development Engineer - 2027"),
        ("Software Engineering Intern - PhD - Summer 2027", "Software Engineering Intern - MS - Summer 2027"),
        ("Current PhD - AI Engineering Internship Program - Summer 2027",
         "Current Master's - AI Engineering Internship Program - Summer 2027"),
        ("Ph.D. Intern - AI/ML & Design Automation", "M.S. Intern - AI/ML & Design Automation"),
    ]
    for x, y in pairs:
        assert not is_fuzzy_match({**base, "title": x}, {**base, "title": y}), (x, y)
    assert is_fuzzy_match({**base, "title": "Software Engineer Intern - Summer 2027"},
                          {**base, "title": "Software Engineering Intern - Summer 2027"})


def test_fuzzy_match_term_guard_needs_a_value_in_both_titles():
    # Only one title names the year: one Workday req (Brevan Howard JR101597) and one gh_jid
    # (Figma 6219995004), so each pair is still one listing (#123).
    bh = {"company": "Brevan Howard", "location": "New York City, NY", "job_type": "internship"}
    assert is_fuzzy_match(
        {**bh, "title": "2027 Summer Internship Program - Systematic Trading Technology Software Engineer - New York"},
        {**bh, "title": "Summer Internship Program - Systematic Trading Technology Software Engineer"})
    figma = {"company": "Figma", "location": "San Francisco, CA", "job_type": "internship"}
    assert is_fuzzy_match({**figma, "title": "PhD Intern, Software Engineer - Graphics (2027)"},
                          {**figma, "title": "PhD Intern - Software Engineer - Graphics 🎓"})


def test_fuzzy_match_term_and_degree_lists_conflict_when_they_differ():
    # Waymo's "PhD" and "MS/PhD" Simulation Realism internships are two postings (gh_jid 8265868
    # and 8208465), so lists that only share a value still conflict. Google's PhD and BS/MS
    # part-time internships share none. The same list in another punctuation still matches (#123).
    base = {"company": "Acme", "location": "London, UK", "job_type": "internship"}
    pairs = [
        ("2027 Summer Intern - PhD - Machine Learning - Simulation Realism",
         "2027 Summer Intern - MS/PhD - Machine Learning - Simulation Realism"),
        ("Part-Time Software Engineering PhD Intern - 2027", "Part-Time Software Engineering BS/MS Intern - 2027"),
        ("Software Engineering Co-op - Fall 2027", "Software Engineering Co-op - Summer/Fall 2027"),
    ]
    for x, y in pairs:
        assert not is_fuzzy_match({**base, "title": x}, {**base, "title": y}), (x, y)
    assert is_fuzzy_match({**base, "title": "2027 Summer Intern - MS/PhD - Software Engineer - Eval Data Infra"},
                          {**base, "title": "2027 Summer Intern, MS/PhD, Software Engineer, Eval Data Infra"})


def test_normalize_location_single_city_aliases():
    assert normalize_location("NYC") == "New York City, NY"
    assert normalize_location("SF") == "San Francisco, CA"
    assert normalize_location(" la ") == "Los Angeles, CA"
    assert normalize_location("Austin, TX") == "Austin, TX"


def test_normalize_location_multi_city_keeps_every_city_and_drops_repeats():
    assert normalize_location("Seattle, WA; SF; NYC") == "Seattle, WA; San Francisco, CA; New York City, NY"
    assert normalize_location("NYC; New York City, NY; ") == "New York City, NY"
    assert normalize_location("Bristol, UK; Bristol, United Kingdom") == "Bristol, UK"


def test_normalize_location_international_city_aliases():
    assert normalize_location("London, United Kingdom") == "London, UK"
    assert normalize_location("Singapore, Singapore") == "Singapore"
    assert normalize_location("Toronto, Canada") == "Toronto, ON, Canada"
    assert normalize_location("Vancouver, Canada") == "Vancouver, BC, Canada"
    # The source's truncated form keeps its `+N` marker and is left alone here.
    assert normalize_location("London, United Kingdom +1") == "London, United Kingdom +1"
    assert normalize_location("Londonderry, UK") == "Londonderry, UK"


def test_normalize_location_arlington_and_hong_kong_spellings():
    assert normalize_location("Arlington, VA") == "Arlington County, Arlington, VA"
    assert normalize_location("Hong Kong, Hong Kong") == "Hong Kong"
    assert normalize_location("Arlington, VA; Arlington County, Arlington, VA") == "Arlington County, Arlington, VA"
    # Another Arlington and the source's truncated cells stay as published (#55).
    for raw in ("Arlington, TX", "Arlington, VA +2", "Hong Kong, Hong Kong +1", "Hong Kong"):
        assert normalize_location(raw) == raw
    for raw in ("Arlington, VA", "Hong Kong, Hong Kong"):
        once = normalize_location(raw)
        assert normalize_location(once) == once


def test_normalize_location_uk_city_spelling():
    assert normalize_location("Bristol, United Kingdom") == "Bristol, UK"
    assert normalize_location("Newcastle upon Tyne, United Kingdom") == "Newcastle upon Tyne, UK"
    assert normalize_location("Remote - Belfast, United Kingdom") == "Remote - Belfast, UK"
    assert normalize_location("Remote in Belfast, United Kingdom") == "Remote - Belfast, UK"
    for raw in ("Remote - United Kingdom", "Remote in United Kingdom", "Remote in UK"):
        assert normalize_location(raw) == "Remote - UK"
    assert normalize_location("United Kingdom") == "United Kingdom"
    assert normalize_location("Bristol, United Kingdom +1") == "Bristol, United Kingdom +1"
    for raw in ("Bristol, United Kingdom", "Remote in Belfast, United Kingdom", "Remote in United Kingdom"):
        once = normalize_location(raw)
        assert normalize_location(once) == once


def test_normalize_location_canadian_city_spelling():
    assert normalize_location("Ottawa, Canada") == "Ottawa, ON, Canada"
    assert normalize_location("Calgary, Canada") == "Calgary, AB, Canada"
    assert normalize_location("Richmond, Canada") == "Richmond, BC, Canada"
    assert normalize_location("Richmond Hill, Canada") == "Richmond Hill, ON, Canada"
    assert normalize_location("Montréal, Canada") == "Montreal, QC, Canada"
    assert normalize_location("Montreal, QC") == "Montreal, QC, Canada"
    assert normalize_location("Mississauga, ON") == "Mississauga, ON, Canada"
    assert normalize_location("Remote - Edmonton, Canada") == "Remote - Edmonton, AB, Canada"
    assert normalize_location("Remote in Toronto, Canada") == "Remote - Toronto, ON, Canada"
    assert normalize_location("Montréal, Canada; Montreal, QC, Canada") == "Montreal, QC, Canada"
    # Province-level cells, cities without a SimplifyJobs spelling, a province code that does
    # not match the city, two-letter codes that are also country codes, and "+N" cells stay.
    for raw in ("Ontario, Canada", "Québec, Canada", "Kanata, Canada", "Cambridge, Canada",
                "Ottawa, QC", "Bratislava, SK", "Amsterdam, NL", "Montréal, Canada +1", "Canada",
                "Remote - Canada"):
        assert normalize_location(raw) == raw
    for raw in ("Montréal, Canada", "Remote in Toronto, Canada", "Ottawa, ON", "Québec City, QC, Canada"):
        once = normalize_location(raw)
        assert normalize_location(once) == once


def test_normalize_location_canadian_spellings_fuzzy_match():
    a = {"company": "Tower Research Capital", "title": "Machine Learning Intern", "job_type": "internship",
         "location": "Montréal, Canada"}
    assert is_fuzzy_match(a, {**a, "location": "Montreal, QC"})


def test_normalize_location_us_country_and_state_aliases():
    assert normalize_location("USA") == "United States"
    assert normalize_location("Iowa, USA") == "Iowa"
    assert normalize_location("North Carolina, USA") == "North Carolina"
    assert normalize_location("Remote - USA") == "Remote - USA"
    assert normalize_location("Austin, TX") == "Austin, TX"
    assert normalize_location("Ontario, USA") == "Ontario, USA"


def test_normalize_location_remote_variants_collapse():
    for raw in ("Remote - USA", "Remote in USA", "Remote, U.S."):
        assert normalize_location(raw) == "Remote - USA"
    assert normalize_location("Remote in Canada") == "Remote - Canada"
    assert normalize_location("Remote") == "Remote"


def test_fuzzy_match_sees_cross_source_location_overlap():
    base = {"company": "Acme", "title": "Software Engineer Intern", "location": "NYC", "job_type": "internship"}
    assert is_fuzzy_match(base, {**base, "location": "New York City, NY"})
    # "city" and two-letter state codes alone are not an overlap
    assert not is_fuzzy_match(base, {**base, "location": "Salt Lake City, UT"})
    assert not is_fuzzy_match({**base, "location": "LA"}, {**base, "location": "Irvine, CA"})


_SAME_ROLE = {"company": "Acme", "title": "Software Engineer Intern", "job_type": "internship"}


def _both_ways(x: str, y: str) -> tuple[bool, bool]:
    a, b = {**_SAME_ROLE, "location": x}, {**_SAME_ROLE, "location": y}
    return is_fuzzy_match(a, b), is_fuzzy_match(b, a)


def test_fuzzy_match_shared_place_name_part_is_not_an_overlap():
    # The first five pairs folded a different role into a record at another place (#128).
    pairs = [
        ("Santa Clara, CA", "Santa Rosa, CA"),
        ("Fort Lauderdale, FL", "Fort Wayne, IN"),
        ("San Francisco, CA", "San Luis Obispo, CA"),
        ("Redondo Beach, CA", "Manhattan Beach, CA"),
        ("San Diego, CA", "Los Angeles, CA; San Mateo, CA"),
        ("Arlington County, Arlington, VA", "Orange County, CA"),
        ("Arlington, VA", "Wake County, NC"),
    ]
    for x, y in pairs:
        assert _both_ways(x, y) == (False, False), (x, y)


def test_fuzzy_match_keeps_overlaps_beyond_place_name_parts():
    pairs = [
        ("Mountain View, CA", "Mountain View, CA +1"),  # only generic words: overlap as before
        ("Salt Lake City, UT", "Salt Lake City, UT +2"),
        ("NYC", "New York City, NY"),
        ("Montréal, Canada", "Montreal, QC"),
        ("Arlington, VA", "Arlington County, Arlington, VA"),
        ("Remote United States of America (+1 more)", "Remote - Marietta, GA"),  # Vanderlande JR38708
    ]
    for x, y in pairs:
        assert _both_ways(x, y) == (True, True), (x, y)


def test_fuzzy_match_generic_only_location_does_not_match_everything():
    for generic in ("Mountain View, CA", "South SF", "West Point, PA", "Valley, NE"):
        assert _both_ways(generic, "Austin, TX") == (False, False), generic
