"""/totaljobs/autocomplete and /totaljobs/searches/popular."""
from totaljobs import fetch
from totaljobs import jobs as J
from totaljobs import parsers as P

AUTOSUGGEST_PATH = "/searchbar/autosuggest/suggest"


def autocomplete(query, limit=10):
    """The search box's job-title suggestions for a partial keyword, with how
    many live postings carry each title."""
    payload = fetch.get_json(AUTOSUGGEST_PATH, {"Text": query, "SiteId": fetch.SITE_ID}, label=f"autosuggest {query!r}")
    return {"query": query, "suggestions": P.autosuggest(payload)[:limit]}


def popular(keyword=None, location=None, radius=None):
    """What the site promotes around a search: the popular keyword searches
    for the place, the nearby locations with live job counts and the related
    skills — for discovery and link building. Without a keyword or location
    it is the UK-wide list."""
    state = J._query(keyword, location, radius)
    out = P.search_results(state)
    return {"search": out["search"], "total_count": out["counts"]["total"],
            "popular_searches": out["related_searches"], "popular_locations": P.popular_locations(state),
            "related_skills": out["related_skills"]}
