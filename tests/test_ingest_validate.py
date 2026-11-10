import json

from scripts import ingest, validate
from scripts.common import save_store


def rec(company, title, url, source="s1", job_type="internship", location="NYC"):
    raw = {"company": company, "title": title, "location": location, "apply_url": url, "url": url,
           "category": "swe", "job_type": job_type, "salary": None, "sponsorship": None,
           "citizenship": None, "_source": {"source": source, "source_url": "https://x"}}
    return ingest.to_record(raw, "2026-10-01")


def test_merge_rejects_exact_and_fuzzy_duplicates_and_appends_sources():
    store = []
    ingest.merge(store, [rec("Acme", "SWE Intern", "https://a.com/1")], "2026-10-01")
    stats = ingest.merge(store, [
        rec("Acme", "SWE Intern", "https://a.com/1?utm_source=z", source="s2"),  # same id
        rec("Acme", "SWE Intern.", "https://a.com/other", source="s2", location="NYC, NY"),  # fuzzy
        rec("Acme", "Data Intern", "https://a.com/2"),  # genuinely new
    ], "2026-10-02")
    assert stats == {"new": 1, "updated": 2, "duplicates_rejected": 2}
    assert len(store) == 2
    assert {s["source"] for s in store[0]["sources"]} == {"s1", "s2"}


def test_merge_fills_missing_category_but_never_overwrites():
    store = []
    ingest.merge(store, [rec("Acme", "Firmware Intern", "https://a.com/1"), rec("Acme", "Data Intern", "https://a.com/2")], "2026-10-01")
    store[0]["category"], store[1]["category"] = None, "ai_ml_data"
    incoming = [rec("Acme", "Firmware Intern", "https://a.com/1"), rec("Acme", "Data Intern", "https://a.com/2")]
    incoming[0]["category"], incoming[1]["category"] = "hardware", "swe"
    ingest.merge(store, incoming, "2026-10-02")
    assert [r["category"] for r in store] == ["hardware", "ai_ml_data"]


def test_close_missing_only_touches_live_sources():
    store = []
    ingest.merge(store, [rec("A", "T1", "https://a/1"), rec("B", "T2", "https://b/1", source="dead")], "2026-10-01")
    closed = ingest.close_missing(store, set(), {"s1"}, "2026-10-02")
    assert closed == 1
    assert {r["company"]: r["status"] for r in store} == {"A": "closed", "B": "open"}


def test_fuzzy_matched_record_is_not_closed():
    store, seen = [], set()
    ingest.merge(store, [rec("Acme", "SWE Intern", "https://a.com/1")], "2026-10-01")
    incoming = [rec("Acme", "SWE Intern.", "https://a.com/other", location="NYC, NY")]
    assert incoming[0]["id"] != store[0]["id"]
    ingest.merge(store, incoming, "2026-10-02", seen)
    assert seen == {store[0]["id"]}
    assert ingest.close_missing(store, seen, {"s1"}, "2026-10-02") == 0
    assert store[0]["status"] == "open" and store[0]["last_seen"] == "2026-10-02"


def test_guard_blocks_large_swings_only():
    assert ingest.guard_ok("x", 100, {}) is True
    assert ingest.guard_ok("x", 120, {"x": 100}) is True
    assert ingest.guard_ok("x", 60, {"x": 100}) is False
    assert ingest.guard_ok("x", 140, {"x": 100}) is False


def test_last_row_counts_skips_backfilled_skip_entries(tmp_path, monkeypatch):
    log = tmp_path / "run-log.json"
    monkeypatch.setattr(ingest, "RUN_LOG", log)
    assert ingest.last_row_counts() == {}
    log.write_text(json.dumps({"runs": [
        {"date": "2026-11-05", "row_counts": {"a": 100}},
        {"date": "2026-11-06", "skipped": True, "row_counts": None},
    ]}))
    prior = ingest.last_row_counts()
    assert prior == {"a": 100}
    assert not ingest.guard_ok("a", 10, prior)
    log.write_text(json.dumps({"runs": [{"date": "2026-11-06", "skipped": True, "row_counts": None}]}))
    assert ingest.last_row_counts() == {}


def test_validate_flags_duplicates_and_bad_schema(tmp_path):
    good = rec("Acme", "SWE Intern", "https://a.com/1")
    path = tmp_path / "jobs.jsonl"
    save_store([good], path)
    assert validate.validate(path) == []
    path.write_text(json.dumps(good) + "\n" + json.dumps(good) + "\n{bad json\n")
    errors = validate.validate(path)
    assert any("duplicate id" in e for e in errors) and any("unparseable" in e for e in errors)
    broken = {k: v for k, v in good.items() if k != "status"}
    path.write_text(json.dumps(broken) + "\n")
    assert any("missing fields" in e for e in validate.validate(path))


def test_committed_store_is_valid():
    assert validate.validate() == []


def test_to_record_normalizes_location():
    assert rec("Acme", "SWE Intern", "https://a.com/1", location="SF; Remote in USA")["location"] == "San Francisco, CA; Remote - USA"


def test_dedupe_consolidates_pairs_into_the_record_seen_first():
    from scripts import dedupe
    old = rec("Acme", "SWE Intern", "https://a.com/1", location="NYC")
    new = rec("Acme", "SWE Intern", "https://a.com/2", source="s2", location="New York City, NY")
    old["first_seen"], old["status"], new["last_seen"] = "2026-09-28", "closed", "2026-10-14"
    survivors, summary = dedupe.consolidate([new, old])
    assert [r["id"] for r in survivors] == [old["id"]]
    assert summary["merged"] == [{"removed": new["id"], "into": old["id"], "company": "Acme", "title": "SWE Intern"}]
    assert survivors[0]["status"] == "open" and survivors[0]["last_seen"] == "2026-10-14"
    assert {s["source"] for s in survivors[0]["sources"]} == {"s1", "s2"}


def test_validate_rejects_unnormalized_location(tmp_path):
    r = rec("Acme", "SWE Intern", "https://a.com/1")
    r["location"] = "NYC"
    save_store([r], tmp_path / "jobs.jsonl")
    assert any("not normalized" in e for e in validate.validate(tmp_path / "jobs.jsonl"))




def test_merge_only_rewrites_location_on_an_id_hit_that_adds_separators():
    store = []
    ingest.merge(store, [rec("Acme", "SWE Intern", "https://a.com/1", location="SFNYC")], "2026-10-01")
    # a fuzzy hit is a different listing and never rewrites location
    ingest.merge(store, [rec("Acme", "SWE Intern", "https://a.com/2", location="Austin, TX; SFNYC")], "2026-10-02")
    assert store[0]["location"] == "SFNYC"
    # the same id moving to another single place keeps the stored value
    ingest.merge(store, [rec("Acme", "SWE Intern", "https://a.com/1", location="Toronto, ON, Canada")], "2026-10-03")
    assert store[0]["location"] == "SFNYC"
    ingest.merge(store, [rec("Acme", "SWE Intern", "https://a.com/1", location="SF; NYC")], "2026-10-04")
    assert store[0]["location"] == "San Francisco, CA; New York City, NY"


def test_id_hit_location_rewrite_that_creates_a_fuzzy_pair_is_consolidated(tmp_path):
    from scripts import dedupe

    def errors(records):
        save_store(records, tmp_path / "jobs.jsonl")
        return validate.validate(tmp_path / "jobs.jsonl")

    store = []
    # two listings of one role: a speedyapply row and a Simplify row whose location was
    # run together before #39, so their location tokens never overlapped
    ingest.merge(store, [rec("KBR", "JR Software Engineer", "https://k.com/1", location="Chantilly, VA +6")], "2026-09-28")
    ingest.merge(store, [rec("KBR", "Junior Software Engineer", "https://k.com/2", source="s2",
                             location="King of Prussia, PAChantilly, VA")], "2026-09-28")
    assert len(store) == 2 and not errors(store)
    # the Simplify row comes back split; the id hit rewrites its location and the pair now overlaps
    ingest.merge(store, [rec("KBR", "Junior Software Engineer", "https://k.com/2", source="s2",
                             location="King of Prussia, PA; Chantilly, VA")], "2026-10-28")
    assert any("fuzzy duplicate" in e for e in errors(store))
    survivors, summary = dedupe.consolidate(store)
    assert len(survivors) == 1 and len(summary["merged"]) == 1
    assert {s["source"] for s in survivors[0]["sources"]} == {"s1", "s2"}
    assert not errors(survivors)


def test_main_prints_the_ids_a_consolidation_removes(monkeypatch, capsys):
    older = rec("KBR", "JR Software Engineer", "https://k.com/1", location="Chantilly, VA +6")
    newer = rec("KBR", "Junior Software Engineer", "https://k.com/2", source="s2",
                location="King of Prussia, PAChantilly, VA")
    newer["first_seen"] = "2026-10-02"
    saved = []
    split = {"company": "KBR", "title": "Junior Software Engineer", "location": "King of Prussia, PA; Chantilly, VA",
             "apply_url": "https://k.com/2", "url": "https://k.com/2", "category": "swe", "job_type": "internship",
             "salary": None, "sponsorship": None, "citizenship": None}
    first = []

    def parse_source(src, offline):
        if first and first[0] != src["name"]:
            return []
        first.append(src["name"])
        return [{**split, "_source": {"source": src["name"], "source_url": src["url"]}}]

    monkeypatch.setattr(ingest, "parse_source", parse_source)
    monkeypatch.setattr(ingest, "last_row_counts", lambda: {})
    monkeypatch.setattr(ingest, "load_store", lambda: [older, newer])
    monkeypatch.setattr(ingest, "save_store", saved.append)
    assert ingest.main(["--today", "2026-10-28"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["consolidated"] == 1
    assert summary["consolidated_ids"] == [{"removed": newer["id"], "into": older["id"]}]
    assert [r["id"] for r in saved[0]] == [older["id"]]
