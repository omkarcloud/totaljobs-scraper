"""Live endpoint smoke tests: one call per /totaljobs/* route against a
running service, with example values proven to return data (2026-10-19).
The listing tooling (derive_facts.py) reads each route's FIRST call from
this file's AST as its working example, so the values stay literals.

Skipped unless TOTALJOBS_BASE points at a running service:

    SCRAPERS_PORT=6071 ONLY_SCRAPER=totaljobs python run.py
    TOTALJOBS_BASE=http://127.0.0.1:6071 python -m pytest totaljobs/test_endpoints.py -q
"""
import os

import pytest

BASE = os.environ.get("TOTALJOBS_BASE", "").rstrip("/")

pytestmark = pytest.mark.skipif(not BASE, reason="set TOTALJOBS_BASE to run live endpoint tests")


def call(path, **params):
    from curl_cffi import requests
    resp = requests.get(BASE + path, params=params, timeout=300)
    assert resp.status_code == 200, f"{path} {params} -> {resp.status_code} {resp.text[:300]}"
    body = resp.json()
    assert body, f"{path} returned an empty body"
    return body


def status(path, **params):
    from curl_cffi import requests
    return requests.get(BASE + path, params=params, timeout=300).status_code


def test_job_search():
    body = call("/totaljobs/jobs/search", keyword="python developer", location="London")
    assert body["count"] >= 25 and len(body["jobs"]) == 25 and body["total_pages"] >= 2 and body["next"]
    job = body["jobs"][0]
    assert job["id"] and job["title"] and job["link"].startswith("https://www.totaljobs.com/job/") and job["company"]["name"]
    assert "site" not in job and body["search"]["radius_unit"] == "miles" and body["search"]["location"] == "London"
    page2 = call("/totaljobs/jobs/search", keyword="python developer", location="London", page=2)
    assert page2["current_page"] == 2 and page2["jobs"] and page2["jobs"][0]["id"] not in {j["id"] for j in body["jobs"]}
    body = call("/totaljobs/jobs/search", keyword="nurse", location="Manchester", radius=20, posted_within="7_days",
                job_type="permanent", salary_min=30000, remote="none", sort="date")
    assert body["jobs"] and body["search"]["filters"] == {"posted_within": "7_days", "job_type": "permanent",
                                                          "salary_min": 30000, "remote": "none"}
    assert body["search"]["sort"] == "date"
    # every filter really narrows the result (2026-10-21: salary needed salarytypeid=1)
    base = call("/totaljobs/jobs/search", keyword="nurse", location="Manchester")["count"]
    for f in ({"posted_within": "3_days"}, {"job_type": "contract"}, {"remote": "full"}, {"salary_min": 40000}):
        assert call("/totaljobs/jobs/search", keyword="nurse", location="Manchester", **f)["count"] < base, f
    # the newer engine ("software engineer" in London): filters translated, posting age refused
    base = call("/totaljobs/jobs/search", keyword="software engineer", location="London")["count"]
    for f in ({"job_type": "permanent"}, {"remote": "full"}, {"salary_min": 60000}):
        narrowed = call("/totaljobs/jobs/search", keyword="software engineer", location="London", **f)
        assert narrowed["count"] < base and narrowed["search"]["filters"] == {k: v for k, v in f.items()}, f
    assert status("/totaljobs/jobs/search", keyword="software engineer", location="London", posted_within="7_days") == 400
    assert call("/totaljobs/jobs/search", location="Leeds")["jobs"]
    assert call("/totaljobs/jobs/search", keyword="python", skill="659280")["search"]["filters"] == {"skill": ["659280"]}
    assert status("/totaljobs/jobs/search") == 400
    assert status("/totaljobs/jobs/search", keyword="python", posted_within="2_days") == 400
    assert status("/totaljobs/jobs/search", keyword="python", job_type="freelance") == 400
    assert status("/totaljobs/jobs/search", keyword="python", company_type="agency") == 400
    assert status("/totaljobs/jobs/search", keyword="python", bogus=1) == 400


def test_job_filters():
    body = call("/totaljobs/jobs/filters", keyword="python developer", location="London")
    assert body["total_count"] >= 25 and body["filters"]
    names = {f["name"] for f in body["filters"]}
    assert {"posted_within", "remote", "job_type", "skill"} <= names and "company_type" not in names
    skill = next(f for f in body["filters"] if f["name"] == "skill")["options"][0]
    assert skill["value"].isdigit() and skill["count"] > 0
    assert body["popular_locations"] and body["popular_locations"][0]["count"] and body["popular_locations"][0]["link"]
    assert body["related_searches"] and body["related_skills"]


def test_job_stats():
    body = call("/totaljobs/jobs/stats", keyword="data analyst", location="Bristol")
    assert body["total_count"] > 10 and len(body["by_posted_within"]) == 4 and body["by_job_type"] and body["top_skills"]
    uk = call("/totaljobs/jobs/stats")
    assert uk["total_count"] > 100000 and uk["counts"]["part_time"] > 10000 and len(uk["popular_locations"]) >= 30


def test_job_details():
    job = call("/totaljobs/jobs/details", job="108167578")
    assert job["id"] == 108167578 and job["title"] and job["description"]["text"] and job["sections"]
    assert job["location"]["country"] == "GB" and job["location"]["latitude"] and job["salary"]["currency"] == "GBP"
    assert job["company"]["id"] == 1231308 and len(job["similar_jobs"]) >= 5 and job["related_searches"]
    by_link = call("/totaljobs/jobs/details", job="https://www.totaljobs.com/job/python-developer/anson-mccade-job108167578")
    assert by_link["id"] == 108167578
    assert status("/totaljobs/jobs/details", job="1") == 404
    assert status("/totaljobs/jobs/details", job="https://www.reed.co.uk/jobs/x/1") == 400


def test_job_batch():
    body = call("/totaljobs/jobs/batch", jobs="108167578,108061802,1")
    assert [j["id"] for j in body["jobs"]] == [108167578, 108061802] and body["not_found"] == [1] and body["errors"] == []
    assert status("/totaljobs/jobs/batch", jobs="1,2,3,4,5,6,7,8,9,10,11") == 400


def test_job_similar():
    body = call("/totaljobs/jobs/similar", job="108167578")
    assert body["job"]["id"] == 108167578 and body["job"]["company"]["name"] and len(body["similar_jobs"]) >= 5
    assert body["similar_jobs"][0]["link"].startswith("https://www.totaljobs.com/job/")


def test_jobs_by_link():
    body = call("/totaljobs/jobs/by-link", link="https://www.totaljobs.com/jobs/nurse/in-manchester?radius=30&postedWithin=7")
    assert body["jobs"] and body["search"]["filters"] == {"posted_within": "7_days"} and body["search"]["radius"] == 30 and body["filters"]
    # a link from the newer engine keeps its own params
    body = call("/totaljobs/jobs/by-link", link="https://www.totaljobs.com/jobs/software-engineer/in-london?ct=611349")
    assert body["jobs"] and body["search"]["filters"] == {"job_type": "permanent"}
    body = call("/totaljobs/jobs/by-link", link="https://www.totaljobs.com/jobs-at/tesco", page=2)
    assert body["current_page"] == 2 and body["jobs"] and body["jobs"][0]["company"]["name"].lower().startswith("tesco")
    assert status("/totaljobs/jobs/by-link", link="https://www.totaljobs.com/job/python-developer/anson-mccade-job108167578") == 400


def test_company_details():
    company = call("/totaljobs/companies/details", company="1231308")
    assert company["id"] == 1231308 and company["name"] == "Anson Mccade" and company["jobs_count"] > 0
    assert company["logo_link"] and company["job_types"] and company["job_skills"] and company["type"] == "agency"
    by_name = call("/totaljobs/companies/details", company="tesco")
    assert by_name["id"] == 1454709 and by_name["name"].lower().startswith("tesco") and by_name["job_locations"]
    assert call("/totaljobs/companies/details", company="Anson Mccade")["id"] == 1231308
    assert call("/totaljobs/companies/details", company="https://www.totaljobs.com/jobs/anson-mccade?cmpId=1231308")["id"] == 1231308
    assert status("/totaljobs/companies/details", company="zzqq-not-a-company") == 404


def test_company_jobs():
    body = call("/totaljobs/companies/jobs", company="https://www.totaljobs.com/jobs-at/tesco", job_type="part_time", sort="date")
    assert body["company"]["id"] == 1454709 and body["jobs"] and body["search"]["filters"] == {"job_type": "part_time"}
    assert all(j["company"]["id"] == 1454709 for j in body["jobs"])
    assert call("/totaljobs/companies/jobs", company="1231308")["jobs"]


def test_autocomplete():
    body = call("/totaljobs/autocomplete", query="pyth")
    assert body["suggestions"] and body["suggestions"][0]["title"].lower().startswith("python") and body["suggestions"][0]["type"] == "job_title"
    assert body["suggestions"][0]["frequency"] >= 1
    assert len(call("/totaljobs/autocomplete", query="nurse", limit=3)["suggestions"]) <= 3
    assert status("/totaljobs/autocomplete") == 400


def test_popular():
    body = call("/totaljobs/searches/popular", location="Manchester")
    assert body["total_count"] > 1000 and body["popular_searches"] and body["popular_searches"][0]["link"]
    assert body["popular_locations"] and body["popular_locations"][0]["id"] and body["related_skills"]
    assert len(call("/totaljobs/searches/popular")["popular_locations"]) >= 30


def test_advice_articles():
    body = call("/totaljobs/advice/articles")
    assert body["topic"]["slug"] == "job-descriptions" and len(body["articles"]) >= 10 and body["total_pages"] >= 10 and body["next"]
    assert body["articles"][0]["title"].endswith("job description") and body["articles"][0]["link"] and body["articles"][0]["read_time_minutes"]
    assert len(body["subtopics"]) >= 20 and body["subtopics"][0]["slug"].endswith("-job-descriptions")
    body = call("/totaljobs/advice/articles", topic="engineering-job-descriptions", page=2)
    assert body["current_page"] == 2 and body["articles"] and body["previous"]
    assert call("/totaljobs/advice/articles", topic="cvs")["articles"]
    assert status("/totaljobs/advice/articles", topic="no-such-topic-zzz") == 404


def test_advice_details():
    article = call("/totaljobs/advice/details", article="sous-chef-job-description")
    assert article["id"] == 10120 and article["title"] == "Sous Chef job description" and article["author"]["name"]
    assert article["read_time_minutes"] and len(article["sections"]) >= 20 and article["faqs"] and article["table_of_contents"]
    assert article["topics"] and article["related_articles"] and article["content"]["text"]
    assert call("/totaljobs/advice/details", article="https://www.totaljobs.com/advice/teacher-job-description")["id"] == 2950
    assert status("/totaljobs/advice/details", article="cvs") == 400
    assert status("/totaljobs/advice/details", article="no-such-article-zzz") == 404


def test_advice_search():
    body = call("/totaljobs/advice/search", query="interview")
    assert len(body["articles"]) == 10 and body["total_pages"] == 2 and body["next"] and body["articles"][0]["summary"]
    page2 = call("/totaljobs/advice/search", query="interview", page=2)
    assert page2["current_page"] == 2 and page2["articles"] and page2["articles"][0]["id"] != body["articles"][0]["id"]
    assert call("/totaljobs/advice/search", query="zzqqxxyy")["articles"] == []
