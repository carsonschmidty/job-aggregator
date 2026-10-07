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
