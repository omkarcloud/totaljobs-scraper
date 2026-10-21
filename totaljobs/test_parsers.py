"""Parser tests on saved pages (totaljobs/fixtures/*.html.gz, fetched
2026-10-17/19 through a GB residential exit) and on the input resolvers. No
network.

    /usr/local/bin/python3.12 -m pytest totaljobs/test_parsers.py -q
"""
import gzip
import os

import pytest

from totaljobs import parsers as P
from totaljobs import refs
from totaljobs.fetch import BadRequest
from totaljobs.jobs import filter_params, new_engine_params

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def html(name):
    with gzip.open(os.path.join(FIXTURES, name + ".html.gz"), "rt", encoding="utf-8") as f:
        return f.read()


def state(name):
    out = P.extract_app(html(name), "app-unifiedResultlist")
    assert out, f"{name}: no result list state"
    return out


# ---- result lists --------------------------------------------------------------------------------

def test_search():
    out = P.search_results(state("search"))
    assert out["search"]["keyword"] == "Python Developer" and out["search"]["location"] == "London"
    assert out["search"]["radius"] == 10 and out["search"]["radius_unit"] == "miles"
    assert "site" not in out["search"] and out["pagination"]["total_count"] == 31 and out["pagination"]["total_pages"] == 2
    job = out["jobs"][0]
    assert job["id"] == 108167578 and job["title"] == "Python Developer" and "site" not in job
    assert job["link"] == "https://www.totaljobs.com/job/python-developer/anson-mccade-job108167578"
    assert job["company"]["id"] == 1231308 and job["company"]["name"] == "Anson Mccade" and job["company"]["logo_link"]
    assert job["salary"] == {"text": "Up to £80,000 per annum", "min": None, "max": 80000, "exact": None,
                             "currency": "GBP", "period": "year", "is_predicted": False}
    assert job["posted_at"] == "2026-10-14T08:48:24Z" and job["expires_at"] and job["match_type"] == "direct"
    assert out["counts"]["total"] == 31 and out["counts"]["nearby"] == 22
    assert out["related_searches"][0]["link"].startswith("https://www.totaljobs.com/jobs/")
    # the fixture was fetched with ?salary=50000&postedWithin=7
    assert out["search"]["filters"] == {"posted_within": "7_days", "salary_min": 50000}
    assert P.applied_filters(state("all_jobs")) == {}


def test_filters_use_uk_words():
    assert P.is_new_engine(state("search_location")) is False
    facets = {f["name"]: f for f in P.filters(state("search_location"))}
    assert set(facets) == {"posted_within", "remote", "job_type", "skill"}     # company_type is not a filter
    company_types = P.all_facets(state("search_location"))["company_type"]
    assert [o["value"] for o in company_types] == ["direct_employer", "agency"]
    assert [o["value"] for o in facets["posted_within"]["options"]] == ["1_day", "3_days", "7_days", "14_days"]
    assert [o["value"] for o in facets["remote"]["options"]] == ["none", "full"]
    assert {o["value"] for o in facets["job_type"]["options"]} == {"permanent", "work_from_home", "part_time", "temporary", "contract"}
    assert facets["skill"]["options"][0]["value"].isdigit() and facets["skill"]["options"][0]["count"] > 0
    assert all(o["count"] > 0 for f in facets.values() for o in f["options"])


def test_popular_locations():
    places = P.popular_locations(state("search_location"))
    assert len(places) >= 30
    assert places[0] == {"id": 66143, "name": "Shirebrook", "count": 90, "link": "https://www.totaljobs.com/jobs/in-shirebrook"}
    assert len({p["name"] for p in places}) == len(places)


def test_stats_uk_wide():
    out = P.stats(state("all_jobs"))
    assert out["total_count"] == 133393 and out["counts"]["part_time"] == 17138 and out["counts"]["temporary"] == 9038
    assert out["search"]["keyword"] is None and out["search"]["location"] is None
    assert sum(r["count"] for r in out["by_job_type"]) > 100000
    assert out["by_posted_within"][0] == {"value": "1_day", "label": "Last 24 hours", "count": 57865}
    assert out["by_remote"][1]["value"] == "full" and out["top_skills"][0]["id"] and out["popular_locations"]


# ---- job page --------------------------------------------------------------------------------------

def test_job_details():
    job = P.job_details(html("job"))
    assert job["id"] == 108167578 and job["title"] == "Python Developer" and "site" not in job
    assert job["contract_type"] == "Permanent Contract; Hybrid" and job["remote"] == "partial"
    assert job["employment_type"] == "FULL_TIME" and job["is_online"] is True and job["is_expired"] is False
    assert job["location"]["city"] == "Central London" and job["location"]["country"] == "GB"
    assert abs(job["location"]["latitude"] - 51.52) < 0.01
    assert job["salary"]["max"] == 80000 and job["salary"]["currency"] == "GBP"
    assert job["description"]["text"].startswith("Python Developer") and "<p>" in job["description"]["html"]
    assert job["sections"][0]["name"] == "jobDescription" and len(job["images"]) == 3
    assert job["company"]["id"] == 1231308 and job["company"]["has_passport"] is False
    assert len(job["similar_jobs"]) == 10 and job["similar_jobs"][0]["id"] == 108061802 and "site" not in job["similar_jobs"][0]
    assert job["related_searches"][0]["type"] == "job_title" and len(job["related_searches"]) >= 20
    assert P.similar_jobs(html("job"))[0]["id"] == 108061802


def test_job_details_not_a_job():
    assert P.job_details(html("search")) is None
    assert P.job_details("<html></html>") is None


# ---- company page ------------------------------------------------------------------------------------

def test_company_details():
    company = P.company_details(html("company"))
    assert company["id"] == 1454709 and company["name"] == "TESCO Plc" and "site" not in company
    assert company["link"] == "https://www.totaljobs.com/jobs/tesco" and company["jobs_count"] == 1547
    assert company["has_passport"] is False and company["is_anonymous"] is False
    assert "job_disciplines" not in company and "job_contract_types" not in company
    assert company["job_types"][0] == {"type": "permanent", "label": "Permanent", "count": 1547}
    assert company["job_skills"][0]["name"] == "Service" and company["job_skills"][0]["id"] == 2382613
    assert len(company["job_locations"]) >= 30 and company["job_locations"][0]["link"].startswith("https://www.totaljobs.com/jobs/tesco/in-")
    assert company["remote_jobs_count"] == 17


def test_company_details_not_a_company():
    assert P.company_details("<html></html>") is None


# ---- autosuggest -------------------------------------------------------------------------------------

def test_autosuggest():
    payload = {"itemCollection": [{"title": "Python Developer", "frequency": 8, "type": "TYPE_JD", "companyId": None, "cityId": None},
                                  {"title": "", "type": "TYPE_JD"}, "junk"]}
    assert P.autosuggest(payload) == [{"title": "Python Developer", "type": "job_title", "frequency": 8}]
    assert P.autosuggest(None) == [] and P.autosuggest({"itemCollection": "x"}) == []


# ---- advice library ------------------------------------------------------------------------------------

def test_advice_article():
    article = P.advice_article(html("advice_article"))
    assert article["id"] == 10120 and article["title"] == "Sous Chef job description"
    assert article["slug"] == "sous-chef-job-description" and article["link"] == "https://www.totaljobs.com/advice/sous-chef-job-description"
    assert article["standfirst"].startswith("If you love cooking") and article["read_time_minutes"] == 36
    assert article["published_at"] == "2020-01-06T09:53:47Z" and article["updated_at"] == "2024-07-15T10:20:27Z"
    assert article["author"] == {"name": "Libby Calaby", "link": "https://www.totaljobs.com/advice/contributor/libby-calaby",
                                 "image_link": "https://www.totaljobs.com/advice/wp-content/uploads/libby-calaby-175x175.jpg"}
    assert article["image_link"].endswith(".jpg")
    assert article["topics"][0]["slug"] == "catering-and-hospitality-job-descriptions" and len(article["topics"]) == 4
    assert article["sections"][0]["title"] == "Introduction" and article["sections"][1]["id"] == "what-is-a-sous-chef"
    assert article["sections"][1]["title"] == "What is a sous chef?" and "under the chef" in article["sections"][1]["text"]
    assert "<p>" in article["sections"][1]["html"] and len(article["sections"]) == 24
    assert article["table_of_contents"][0] == {"id": "what-is-a-sous-chef", "title": "What is a sous chef?"}
    assert len(article["faqs"]) == 4 and article["faqs"][0]["question"] == "Is sous chef a high position?"
    assert article["faqs"][0]["answer"].startswith("Being a sous chef can certainly")
    assert "Sous chef salary" in article["content"]["text"] and article["content"]["html"].startswith("<p>")
    related = article["related_articles"]
    assert related and related[0]["id"] == 2923 and related[0]["slug"] == "kitchen-porter-job-description"
    assert all(a["slug"] != "sous-chef-job-description" for a in related)
    assert related[0]["summary"].startswith("Learn about:\n- What does a Kitchen Porter do?") and related[0]["read_time_minutes"] == 8
    assert related[0]["topics"] == ["career-advice", "what-job-can-i-do", "job-descriptions", "catering-and-hospitality-job-descriptions"]


def test_advice_article_not_an_article():
    assert P.advice_article(html("advice_topic")) is None
    assert P.advice_article("<html></html>") is None


def test_advice_topic_listing():
    out = P.advice_listing(html("advice_topic"))
    assert out["topic"]["name"] == "Engineering job descriptions" and out["topic"]["slug"] == "engineering-job-descriptions"
    assert out["topic"]["description"].startswith("Engineering plays a vital role")
    assert len(out["articles"]) == 12 and out["articles"][0]["id"] == 3121
    assert out["articles"][0]["title"] == "Defence Engineer job description" and out["articles"][0]["read_time_minutes"] == 4
    assert out["subtopics"] == []
    assert out["related_topics"][0]["slug"] == "career-advice" and out["related_topics"][0]["description"]
    assert out["pagination"] == {"page": 1, "items_per_page": 12, "total_count": None, "total_pages": 2}


def test_advice_hub_subtopics():
    out = P.advice_listing(html("advice_hub"))
    assert out["topic"]["slug"] == "job-descriptions" and len(out["articles"]) == 12
    names = [s["slug"] for s in out["subtopics"]]
    assert "engineering-job-descriptions" in names and "retail-job-descriptions" in names and len(names) >= 20
    assert out["pagination"]["total_pages"] == 22


def test_advice_search_listing():
    out = P.advice_listing(html("advice_search"))
    assert len(out["articles"]) == 10 and out["articles"][0]["id"] == 20875
    assert out["articles"][0]["summary"].startswith("Everything you need to know")
    assert out["articles"][0]["topics"] == ["applying-for-a-job", "interviews"]
    assert out["pagination"]["total_pages"] is None


def test_advice_listing_empty_page():
    out = P.advice_listing("<html><body></body></html>")
    assert out["articles"] == [] and out["subtopics"] == [] and out["topic"]["name"] is None


# ---- filter params -------------------------------------------------------------------------------------

def test_filter_params():
    assert filter_params({"posted_within": "7_days", "remote": "full", "job_type": "contract",
                          "salary_min": 40000, "skill": ["659280", "671433"]}) == {
        "postedWithin": "7", "wfh": "1", "tjg_job_type_id": "20", "salary": 40000,
        "salarytypeid": "1", "fsk": "659280,671433"}
    assert filter_params({"posted_within": None, "skill": []}) == {}


def test_new_engine_params():
    assert new_engine_params({"remote": "full", "salary_min": 60000, "skill": ["240010"]}) == {
        "wp": "611350", "us": 60000, "fsk": "240010"}
    assert new_engine_params({"job_type": "permanent"}) == {"ct": "611349"}
    assert new_engine_params({"job_type": "part_time"}) == {"wt": "80002"}
    assert new_engine_params({"job_type": "work_from_home", "remote": "full"}) == {"wp": "611350"}
    with pytest.raises(BadRequest, match="posting date"):
        new_engine_params({"posted_within": "7_days"})
    with pytest.raises(BadRequest, match="conflicts"):
        new_engine_params({"job_type": "work_from_home", "remote": "none"})


# ---- the newer StepStone engine (2026-10-21: "software engineer" in London) ---------------------

def test_new_engine_facets():
    st = state("search_new_engine")
    assert P.is_new_engine(st) is True
    facets = {f["name"]: f for f in P.filters(st)}
    assert set(facets) == {"remote", "job_type", "salary_min", "skill"}       # no posted_within: not filterable there
    assert [o["value"] for o in facets["remote"]["options"]] == ["none", "full"]
    assert {o["value"] for o in facets["job_type"]["options"]} == {"permanent", "contract", "temporary"}
    assert facets["salary_min"]["options"][0]["value"] == 10000
    assert facets["skill"]["options"][0]["value"].isdigit()
    out = P.stats(st)
    assert out["total_count"] > 100 and {r["value"] for r in out["by_remote"]} == {"none", "hybrid", "full"}
    assert [r["value"] for r in out["by_posted_within"]] == ["30_days", "7_days", "1_day"]
    assert out["by_job_type"][0]["value"] == "permanent" and out["by_company_type"] == []
    assert out["popular_locations"] and out["top_skills"][0]["id"]
    jobs = P.search_results(st)["jobs"]
    assert len(jobs) == 25 and jobs[0]["link"].startswith("https://www.totaljobs.com/job/")


# ---- resolvers -------------------------------------------------------------------------------------------

def test_resolve_job():
    assert refs.resolve_job("108167578") == {"id": 108167578}
    assert refs.resolve_job("https://www.totaljobs.com/job/python-developer/anson-mccade-job108167578") == {"id": 108167578}
    assert refs.resolve_job("totaljobs.com/job/x/x-job108167578?WT.mc_id=x") == {"id": 108167578}
    with pytest.raises(ValueError, match="Only totaljobs.com"):
        refs.resolve_job("https://www.reed.co.uk/jobs/python-developer/55555555")
    with pytest.raises(ValueError):
        refs.resolve_job("https://www.totaljobs.com/jobs/python/in-london")
    assert refs.resolve_jobs("108167578, https://www.totaljobs.com/job/a/b-job108061802,108167578") == [{"id": 108167578}, {"id": 108061802}]
    with pytest.raises(ValueError, match="At most 2"):
        refs.resolve_jobs("1,2,3", 2)


def test_resolve_company():
    assert refs.resolve_company("1231308") == {"id": 1231308, "slug": None, "name": None}
    assert refs.resolve_company("anson-mccade-1231308") == {"id": 1231308, "slug": "anson-mccade", "name": None}
    assert refs.resolve_company("https://www.totaljobs.com/jobs/anson-mccade?cmpId=1231308&cmp=1") == {"id": 1231308, "slug": "anson-mccade", "name": None}
    assert refs.resolve_company("https://www.totaljobs.com/jobs-at/tesco") == {"id": None, "slug": "tesco", "name": None}
    assert refs.resolve_company("https://www.totaljobs.com/jobs/tesco?cmp=1") == {"id": None, "slug": "tesco", "name": None}
    assert refs.resolve_company("Anson  Mccade") == {"id": None, "slug": "anson-mccade", "name": "Anson Mccade"}
    assert refs.resolve_company("Studio 3") == {"id": None, "slug": "studio-3", "name": "Studio 3"}
    with pytest.raises(ValueError):
        refs.resolve_company("https://www.totaljobs.com/jobs/python/in-london")
    with pytest.raises(ValueError):
        refs.resolve_company("https://www.stepstone.de/cmp/de/bmw-group-27361/jobs")


def test_resolve_listing():
    out = refs.resolve_listing("https://www.totaljobs.com/jobs/python/in-london?radius=30&postedWithin=7&page=3&rltr=x")
    assert out == {"path": "/jobs/python/in-london", "query": {"postedWithin": ["7"], "radius": ["30"]}}
    assert refs.resolve_listing("https://www.totaljobs.com/jobs-at/tesco") == {"path": "/jobs/tesco", "query": {"cmp": ["1"]}}
    with pytest.raises(ValueError, match="single job"):
        refs.resolve_listing("https://www.totaljobs.com/job/python-developer/anson-mccade-job108167578")
    with pytest.raises(ValueError):
        refs.resolve_listing("https://www.totaljobs.com/advice/cvs")
    with pytest.raises(ValueError):
        refs.resolve_listing("python developer")


def test_resolve_advice():
    assert refs.resolve_article("sous-chef-job-description") == "sous-chef-job-description"
    assert refs.resolve_article("https://www.totaljobs.com/advice/sous-chef-job-description/") == "sous-chef-job-description"
    assert refs.resolve_topic("Engineering-Job-Descriptions") == "engineering-job-descriptions"
    with pytest.raises(ValueError):
        refs.resolve_article("https://www.totaljobs.com/jobs/python")
    with pytest.raises(ValueError):
        refs.resolve_article("not a slug!")
