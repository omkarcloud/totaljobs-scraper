"""Totaljobs input parsing: ONE param per input that auto-detects its forms
(tripadvisor QueryOrLinkField convention, never a sibling `url`/`id` pair).
Every resolver returns plain JSON values (so validated params stay usable as
a response-cache key) and raises ValueError with a user-facing message.

  job       108167578 | https://www.totaljobs.com/job/python-developer/anson-mccade-job108167578
                                                      -> {"id": 108167578}
  company   1231308 | anson-mccade-1231308 | anson-mccade | "Anson Mccade"
            | https://www.totaljobs.com/jobs/anson-mccade?cmpId=1231308&cmp=1
            | https://www.totaljobs.com/jobs-at/anson-mccade
                                  -> {"id": 1231308 | None, "slug": "anson-mccade" | None, "name": "Anson Mccade" | None}
            (`name` is the text as typed — the site's employer-name match is case-sensitive)
  link      any totaljobs.com search / company listing URL
                                                      -> {"path": "/jobs/…", "query": {…}}
  article   sous-chef-job-description | https://www.totaljobs.com/advice/sous-chef-job-description
                                                      -> "sous-chef-job-description"
  topic     job-descriptions | engineering-job-descriptions | https://www.totaljobs.com/advice/cvs
                                                      -> "job-descriptions"
"""
import re
from urllib.parse import parse_qs, unquote, urlparse

HOSTS = {"www.totaljobs.com", "totaljobs.com"}
_ID_RE = re.compile(r"^\d{1,12}$")
_JOB_RE = re.compile(r"-job(\d{3,12})(?:$|[/?#])", re.I)
_SLUG_ID_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._&' \-]*?)[-_ ](\d{4,12})$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,150}$")
_BAD_CHARS = re.compile(r"[/?#\\<>\"]")
SEARCH_PREFIXES = ("/jobs", "/jobs-at")

JOB_HINT = "Must be a Totaljobs job id (e.g. 108167578) or a job link (https://www.totaljobs.com/job/…-job108167578)."
COMPANY_HINT = ("Must be a Totaljobs company id (1231308, the company.id of any job), 'slug-id' (anson-mccade-1231308), "
                "a company name / slug (anson-mccade), or a company link (…/jobs/anson-mccade?cmpId=1231308, "
                "…/jobs-at/anson-mccade).")
LINK_HINT = "Must be a totaljobs.com job search or company listing link (https://www.totaljobs.com/jobs/…)."
ARTICLE_HINT = "Must be an advice article slug (sous-chef-job-description) or link (https://www.totaljobs.com/advice/…)."
TOPIC_HINT = "Must be an advice topic slug (job-descriptions, cvs, interviews, engineering-job-descriptions) or its link."


def slugify(value):
    """'Anson Mccade' -> 'anson-mccade' (the site's own path words)."""
    words = (value or "").strip().lower().replace("&", " and ")
    words = "".join(ch if ch.isalnum() or ch in " -" else " " for ch in words)
    return "-".join(w for w in words.replace("-", " ").split() if w)


def _parse_url(value):
    """-> (path, query dict) for a totaljobs.com URL / host path; None when
    the value is not URL-like; ValueError for another site."""
    raw = (value or "").strip()
    low = raw.lower()
    if low.startswith("//"):
        raw = "https:" + raw
    elif not low.startswith(("http://", "https://")):
        head = low.split("/", 1)[0]
        if head not in HOSTS:
            return None
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host not in HOSTS:
        raise ValueError(f"Only totaljobs.com links are accepted (got '{host}').")
    return unquote(parsed.path), parse_qs(parsed.query)


# ---- jobs -----------------------------------------------------------------------------------

def resolve_job(value):
    raw = (value or "").strip()
    if _ID_RE.match(raw):
        return {"id": int(raw)}
    try:
        url = _parse_url(raw)
    except ValueError as e:
        raise ValueError(f"{e} {JOB_HINT}")
    if not url:
        raise ValueError(JOB_HINT)
    path, query = url
    match = _JOB_RE.search(path)
    if match:
        return {"id": int(match.group(1))}
    for name in ("id", "jobId", "offerId"):
        for candidate in query.get(name, []):
            if _ID_RE.match(candidate.strip()):
                return {"id": int(candidate.strip())}
    raise ValueError(JOB_HINT)


def resolve_jobs(value, max_items=10):
    out = []
    for item in str(value or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            job = resolve_job(item)
        except ValueError as e:
            raise ValueError(f"'{item}': {e}")
        if job not in out:
            out.append(job)
    if not out:
        raise ValueError("Must list at least one job id or link (comma-separated).")
    if len(out) > max_items:
        raise ValueError(f"At most {max_items} jobs.")
    return out


# ---- companies -------------------------------------------------------------------------------

def _slug(value):
    slug = slugify(value)
    if not slug or len(slug) > 150:
        return None
    return slug


def resolve_company(value):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(COMPANY_HINT)
    if _ID_RE.match(raw):
        return {"id": int(raw), "slug": None, "name": None}
    try:
        url = _parse_url(raw)
    except ValueError as e:
        raise ValueError(f"{e} {COMPANY_HINT}")
    if url:
        path, query = url
        segments = [s for s in path.split("/") if s]
        slug = _slug(segments[1]) if len(segments) >= 2 and segments[0] in ("jobs", "jobs-at") else None
        for candidate in query.get("cmpId", []):
            if _ID_RE.match(candidate.strip()):
                return {"id": int(candidate.strip()), "slug": slug, "name": None}
        if slug and segments[0] in ("jobs", "jobs-at") and len(segments) == 2 and not slug.startswith("in-"):
            return {"id": None, "slug": slug, "name": None}
        raise ValueError("Totaljobs company links are …/jobs/<company>?cmpId=<id> or …/jobs-at/<company>. " + COMPANY_HINT)
    match = _SLUG_ID_RE.match(raw)
    if match:
        return {"id": int(match.group(2)), "slug": _slug(match.group(1)), "name": None}
    if _BAD_CHARS.search(raw):
        raise ValueError(COMPANY_HINT)
    slug = _slug(raw)
    if not slug:
        raise ValueError(COMPANY_HINT)
    return {"id": None, "slug": slug, "name": " ".join(raw.split())}


# ---- listing pages ------------------------------------------------------------------------------

def resolve_listing(value):
    raw = (value or "").strip()
    try:
        url = _parse_url(raw)
    except ValueError as e:
        raise ValueError(f"{e} {LINK_HINT}")
    if not url:
        raise ValueError(LINK_HINT)
    path, query = url
    path = path.rstrip("/") or "/"
    if _JOB_RE.search(path):
        raise ValueError("That is a single job's link — use /totaljobs/jobs/details for it.")
    if path != "/" and not any(path == p or path.startswith(p + "/") or path.startswith(p + "?") for p in SEARCH_PREFIXES):
        raise ValueError("The link must be a job search or company listing page (/jobs/…, /jobs-at/…). " + LINK_HINT)
    if path.startswith("/jobs-at/"):
        # /jobs-at/<company> is the site's redirect to /jobs/<company>?cmp=1
        path = "/jobs/" + path[len("/jobs-at/"):]
        query = {**query, "cmp": ["1"]}
    return {"path": path, "query": {k: v for k, v in sorted(query.items()) if k not in ("page", "rltr", "siteId", "action")}}


# ---- advice ---------------------------------------------------------------------------------------

def _advice_slug(value, hint):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(hint)
    try:
        url = _parse_url(raw)
    except ValueError as e:
        raise ValueError(f"{e} {hint}")
    if url:
        path = url[0].rstrip("/")
        if not path.startswith("/advice/"):
            raise ValueError("The link must be an advice page (https://www.totaljobs.com/advice/…). " + hint)
        raw = path[len("/advice/"):]
        if "/" in raw:
            raise ValueError(hint)
    slug = raw.lower().strip("/")
    if not _SLUG_RE.match(slug):
        raise ValueError(hint)
    return slug


def resolve_article(value):
    return _advice_slug(value, ARTICLE_HINT)


def resolve_topic(value):
    return _advice_slug(value, TOPIC_HINT)
