"""/totaljobs/companies/* — an employer's profile and its open jobs, both
from the company jobs page /jobs/<slug>?cmpId=<id>&cmp=1 (the same result
list state as a search plus the company passport when the employer has one).

A company known only by name goes through a keyword search for the name
(/jobs?q=<name>, which also matches employer names — the site's own
/jobs-at/<slug> redirect is the same trick) and takes the company id of the
first result whose employer name matches, so `company=tesco` works without
an id; the id of any job's `company.id` is the reliable key.
"""
from stepstone import sites as S
from totaljobs import fetch
from totaljobs import jobs as J
from totaljobs import parsers as P
from totaljobs.refs import slugify


def _lookup_id(slug, name=None):
    """/jobs?q=<name> (the keyword search also matches employer names, case-
    sensitively: 'Anson Mccade' finds the agency, 'anson mccade' does not)
    -> the company id of the first result whose employer name slugifies to
    `slug`. Tries the name as typed, then Title Case from the slug."""
    candidates = []
    for candidate in (name, " ".join(w.capitalize() for w in slug.split("-")), slug.replace("-", " ")):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        state = J._result_list("/jobs", {"q": candidate}, f"company lookup {candidate!r}")
        companies = {}
        for job in P.search_results(state)["jobs"]:
            company = job.get("company") or {}
            if company.get("id"):
                companies.setdefault(company["id"], slugify(company.get("name")))
        for company_id, company_slug in companies.items():          # exact name: Anson Mccade
            if company_slug == slug:
                return company_id
        for company_id, company_slug in companies.items():          # name plus a suffix: tesco -> TESCO Plc
            if company_slug.startswith(slug + "-"):
                return company_id
    raise fetch.NotFound(f"Totaljobs has no employer named '{name or slug}' — pass the company id (the company.id of any of its jobs)")


def _path(company):
    company_id = company.get("id") or _lookup_id(company["slug"], company.get("name"))
    return company_id, S.company_path(fetch.SITE, company_id, company.get("slug"))


def details(company):
    """One employer by id, slug-id, name or link: profile (passport fields
    when the employer has one), logo, direct-employer / agency type, live job
    count, and where / what kind / which skills its jobs are."""
    company_id, path = _path(company)
    resp = fetch.page(path, label=f"company {company_id}")
    data = P.company_details(resp.text, company_id)
    if not data or not data.get("name"):
        raise fetch.NotFound(f"Totaljobs has no company {company_id}")
    return data


def jobs(company, radius=None, sort="relevance", page=1, **filters):
    """One page (25) of an employer's live jobs, with the search filters."""
    from stepstone import jobs as _st_jobs
    company_id, path = _path(company)
    base = {"radius": radius, "page": page if page > 1 else None, **_st_jobs._sort_params(sort)}
    state, applied = J._list(path, base, filters, f"company {company_id} jobs")
    out = J._with_applied(P.search_results(state), applied)
    out["search"]["sort"] = sort
    first = next((j for j in out["jobs"] if j["company"].get("id")), None)
    out["company"] = {"id": company_id, "name": (first or {}).get("company", {}).get("name") or out["search"].get("keyword"),
                      "link": P.clean_link(fetch.link(path), fetch.SITE)}
    out["filters"] = P.filters(state)
    return J._finish(out, page)
