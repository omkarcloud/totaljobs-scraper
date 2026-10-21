"""/totaljobs/jobs/* — job search with the site's filters, the facets with
counts, a job by id / link, a batch, the recommender's similar jobs, any
listing page by link and market stats, all from the pages' embedded state
(totaljobs/parsers.py over stepstone/parsers.py).

A search page is /jobs/<keyword-slug>/in-<location-slug>?radius=…&page=N
plus one query param per filter. Pages hold 25 jobs (the site ignores
`limit`) and stop at 5,000 results = 200 pages.

Two engines answer a search (2026-10-21, parsers.is_new_engine): the UK one
(most queries) takes PARAMS; Totaljobs' newer StepStone engine (some queries,
e.g. "software engineer" in London) ignores those silently and takes
NEW_ENGINE_PARAMS instead — the two sets cannot share one request (the new
engine's `us` returns 0 jobs on the UK one). _list fetches with the UK
params and, when the page came from the new engine and filters were asked
for, fetches again with the translated ones. Upstream gaps, measured:
the new engine cannot filter by posting date (`postedWithin=age_7`, the
param its own facet links use, makes the server drop the connection; `ag`
is accepted and changes nothing) -> 400; Totaljobs' companytypes filter
changes nothing on either engine, so company type is a count (stats,
company profile), not a filter.
"""
from stepstone import jobs as _st_jobs
from stepstone import sites as S
from totaljobs import fetch
from totaljobs import parsers as P

PER_PAGE = 25
MAX_PAGES = 200

# public param -> (site URL key, value map or None for pass-through ids), UK engine
PARAMS = {
    "posted_within": ("postedWithin", {"1_day": "1", "3_days": "3", "7_days": "7", "14_days": "14"}),
    "remote": ("wfh", {"full": "1", "none": "0"}),
    "job_type": ("tjg_job_type_id", {"permanent": "10", "contract": "20", "temporary": "2", "part_time": "40",
                                     "work_from_home": "50"}),
    "salary_min": ("salary", None),
    "skill": ("fsk", None),
}
FILTER_KEYS = tuple(PARAMS)

# the same public params on the newer StepStone engine: (URL key, value) per value
NEW_ENGINE_PARAMS = {
    "remote": {"full": ("wp", "611350"), "none": ("wp", "611347")},
    "job_type": {"permanent": ("ct", "611349"), "temporary": ("ct", "611348"), "contract": ("ct", "617608"),
                 "part_time": ("wt", "80002"), "work_from_home": ("wp", "611350")},
}


def _active(filters):
    return {k: v for k, v in filters.items() if v not in (None, "", [])}


def filter_params(filters):
    """{public param: value} -> the UK engine's URL params."""
    out = {}
    for name, value in _active(filters).items():
        key, mapping = PARAMS[name]
        if mapping is not None:
            value = mapping[str(value)]
        elif isinstance(value, list):
            value = ",".join(str(v) for v in value)
        out[key] = value
    if "salary" in out:
        out["salarytypeid"] = "1"       # 1 = per annum; without it the salary floor is ignored
    return out


def new_engine_params(filters):
    """{public param: value} -> the newer engine's URL params; BadRequest for
    a filter that engine cannot apply."""
    out = {}
    for name, value in _active(filters).items():
        if name == "posted_within":
            raise fetch.BadRequest("Totaljobs answers this search from its newer search engine, which cannot filter "
                                   "by posting date. Leave out posted_within and use sort=date for the newest jobs first.")
        if name in NEW_ENGINE_PARAMS:
            key, token = NEW_ENGINE_PARAMS[name][str(value)]
            if key in out and out[key] != token:
                raise fetch.BadRequest(f"{name}={value} conflicts with another filter on this search.")
            out[key] = token
        elif name == "salary_min":
            out["us"] = value
        elif name == "skill":
            out["fsk"] = ",".join(str(v) for v in value) if isinstance(value, list) else value
    return out


def search_path(keyword=None, location=None):
    return S.search_path(fetch.SITE, keyword, location)


def _result_list(path, params, label):
    resp = fetch.page(path, params, label=label)
    state = P.extract_app(resp.text, "app-unifiedResultlist")
    if not state:
        raise fetch.UpstreamError(f"no result list in the page for {label} (landed on {resp.url})")
    return state


def _finish(out, page):
    pagination = out["pagination"]
    pagination["page"] = page
    pagination["items_per_page"] = PER_PAGE
    if pagination.get("total_pages") is not None:
        pagination["total_pages"] = min(pagination["total_pages"], MAX_PAGES)
    return out


def _list(path, base, filters, label):
    """A result list with `filters` applied on whichever engine answers:
    UK params first; when the page came from the newer engine and filters
    were asked for, again with that engine's params. Returns (state,
    applied public filters)."""
    active = _active(filters)
    state = _result_list(path, {**base, **filter_params(active)}, label)
    if active and P.is_new_engine(state):
        state = _result_list(path, {**base, **new_engine_params(active)}, label + " (new engine)")
    return state, active


def _query_state(keyword, location, radius, page=None, sort=None, **filters):
    base = {"radius": radius, "page": page if page and page > 1 else None,
            **(_st_jobs._sort_params(sort) if sort else {})}
    label = f"jobs {keyword!r} in {location!r}" + (f" page {page}" if page and page > 1 else "")
    return _list(search_path(keyword, location), base, filters, label)


def _query(keyword, location, radius, page=None, sort=None, **filters):
    return _query_state(keyword, location, radius, page=page, sort=sort, **filters)[0]


def _with_applied(out, applied):
    """search.filters = the public filters this call applied (both engines
    echo them differently, the new one not at all for work policy)."""
    out["search"]["filters"] = dict(applied)
    return out


def search(keyword=None, location=None, radius=None, sort="relevance", page=1, **filters):
    """One page (25 jobs) of a job search."""
    state, applied = _query_state(keyword, location, radius, page=page, sort=sort, **filters)
    out = _with_applied(P.search_results(state), applied)
    out["search"]["sort"] = sort
    return _finish(out, page)


def filters(keyword=None, location=None, radius=None, **filters):
    """The facets of a search with option values and counts (posting age,
    remote, job type, salary floors, top skills), the nearby locations with
    counts and the popular related searches."""
    state, applied = _query_state(keyword, location, radius, **filters)
    out = _with_applied(P.search_results(state), applied)
    return {"search": out["search"], "total_count": out["counts"]["total"], "counts": out["counts"],
            "filters": P.filters(state), "popular_locations": P.popular_locations(state),
            "related_searches": out["related_searches"], "related_skills": out["related_skills"]}


def stats(keyword=None, location=None, radius=None, **filters):
    """Market size for a query (no rows): totals and every facet's breakdown.
    Without keyword or location it is the whole UK board."""
    state, applied = _query_state(keyword, location, radius, **filters)
    out = P.stats(state)
    out["search"]["filters"] = dict(applied)
    return out


def _page(job):
    resp = fetch.page(S.job_path(fetch.SITE, job["id"]), label=f"job {job['id']}")
    return resp.text


def _details(job):
    data = P.job_details(_page(job), job["id"])
    if not data:
        raise fetch.NotFound(f"Totaljobs has no job {job['id']} (expired or removed)")
    return data


def details(job):
    """One job by id or link: full description (sections, text and HTML),
    contract / work type, hybrid / remote flag, salary, location with
    coordinates, the employer's card and passport, similar jobs and related
    searches."""
    return _details(job)


def batch(jobs):
    """Up to 10 jobs in parallel; expired ids are listed in not_found,
    other failures in errors."""
    results = fetch.run_parallel([lambda j=j: _details(j) for j in jobs])
    found, not_found, errors = [], [], []
    for job, (status, value) in zip(jobs, results):
        if status == "ok":
            found.append(value)
        elif isinstance(value, fetch.NotFound):
            not_found.append(job["id"])
        else:
            errors.append({"id": job["id"], "error": str(value)})
    if not found and errors and not not_found:
        raise fetch.UpstreamError("; ".join(e["error"] for e in errors))
    return {"jobs": found, "not_found": not_found, "errors": errors}


def similar(job):
    """The 10 jobs Totaljobs recommends next to one job ("popular with other
    job seekers"), with the job they belong to."""
    html = _page(job)
    data = P.job_details(html, job["id"])
    if not data:
        raise fetch.NotFound(f"Totaljobs has no job {job['id']} (expired or removed)")
    return {"job": {"id": data["id"], "title": data["title"], "link": data["link"],
                    "company": {"id": data["company"]["id"], "name": data["company"]["name"]}},
            "similar_jobs": data["similar_jobs"], "related_searches": data["related_searches"]}


def by_link(link, page=1):
    """The jobs of any totaljobs.com search or company listing link (saved
    searches with the site's own filters), page by page, with its facets."""
    params = dict(link["query"])
    if page > 1:
        params["page"] = page
    resp = fetch.page(link["path"], params, label=f"listing {link['path']}")
    state = P.extract_app(resp.text, "app-unifiedResultlist")
    if not state:
        raise fetch.BadRequest(f"{link['path']} is not a job listing page on Totaljobs")
    out = P.search_results(state)
    out["filters"] = P.filters(state)
    out["popular_locations"] = P.popular_locations(state)
    return _finish(out, page)
