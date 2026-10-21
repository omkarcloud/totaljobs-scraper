"""Raw totaljobs.com pages -> clean API objects. Pure functions, no network;
every parser tolerates missing / null / wrong-typed input and never raises
on a partial page.

The job-board pages are the StepStone stack, so their parsers are
stepstone/parsers.py pinned to the totaljobs row (search_results,
job_details, company_details, autosuggest) with the UK vocabulary applied on
top: job_type / company_type / remote option ids become words, the `site`
key the multi-board scraper carries is dropped, and the UK-only facets the
shared parser ignores are exposed — locationFacet / popularLocations
(nearby places with ids and counts), relatedJobs (popular keyword searches,
already `related_searches`) and the per-facet counts behind /jobs/stats.

The advice library (/advice/…) is WordPress HTML (theme stst-editorial):
article cards (<article class="card post-<id> … category-<slug>">), a
`body_text` div split on <h2> for the sections, schema.org FAQ blocks, the
contributor box, the related-topics tag list and the page-numbers
pagination. Parsed with regexes + a div-balancing scan (no DOM library in
the image).

Two result-list engines (seen 2026-10-21): most searches come back in the
UK layout (facets age / workFromHome / jobTypes / companyTypes / skills /
locationFacet); some (e.g. "software engineer" in London) come back from
Totaljobs' newer StepStone engine (age / unifiedSalary / workPolicy /
contractTypes / skills / categories / sectors / cities / regions /
applicationMethod / popularLocations). is_new_engine() tells them apart;
both are mapped onto the same public filter words, so a facet option's
`value` is always what the same-named search param takes.

Intentionally dropped: everything stepstone/parsers.py drops (tracking
params, optimizely / amplitude blobs, UI labels, filter open/expanded
state, pagination link templates, per-size logo variants) plus, on
totaljobs: the commuteTime facet (empty option list, URL param not exposed
by the page), the autosuggest companyId / cityId / parentLocation /
brandId fields (always null on the UK board — it only suggests job titles),
company_details' discipline / contract-type facets (the UK board has none),
advice card srcset size variants (one image link kept), share buttons,
"continue or read again" widgets, jumbotron promos and the WordPress feed /
wp-json links.
"""
import re
from html import unescape

from stepstone import parsers as P
from stepstone.shared import as_dict, as_list, g, html_to_text, iso_datetime, text, to_int
from totaljobs.fetch import SITE, link as site_link

JOB_TYPE_VALUES = {"10": "permanent", "20": "contract", "2": "temporary", "40": "part_time", "50": "work_from_home"}
COMPANY_TYPE_VALUES = {"2": "direct_employer", "1": "agency"}
REMOTE_VALUES = {"0": "none", "1": "full"}
OPTION_VALUES = {"job_type": JOB_TYPE_VALUES, "company_type": COMPANY_TYPE_VALUES, "remote": REMOTE_VALUES}

# the newer StepStone engine: its option ids -> the same public words
NEW_ENGINE_MARKERS = {"unifiedSalary", "contractTypes", "workPolicy", "herdwickDisciplines"}
NEW_CONTRACT_TYPES = {"611349": "permanent", "611348": "temporary", "617608": "contract"}
NEW_WORK_TYPES = {"80002": "part_time"}
NEW_WORK_POLICIES = {"611350": "full", "611347": "none", "611351": "hybrid"}
NEW_AGE_VALUES = {"age_1": "1_day", "age_7": "7_days", "age_30": "30_days"}

# the filters a search accepts (schemas._JobFilters); company_type is
# informational only: Totaljobs' own companytypes filter changes nothing
PUBLIC_FILTERS = ("posted_within", "remote", "job_type", "salary_min", "skill")

ADVICE_ROOT = "https://www.totaljobs.com/advice/"

extract_app = P.extract_app
clean_link = P.clean_link


# ---- shared post-processing ---------------------------------------------------------------------

def strip_site(obj):
    """Drop the `site` key the multi-board parsers put on jobs, searches and
    companies (every object here is totaljobs.com)."""
    if isinstance(obj, dict):
        return {k: strip_site(v) for k, v in obj.items() if k != "site"}
    if isinstance(obj, list):
        return [strip_site(v) for v in obj]
    return obj


def _words(name, value):
    table = OPTION_VALUES.get(name)
    if table is None or value is None:
        return value
    return table.get(str(value), value)


# ---- result lists ---------------------------------------------------------------------------------

SELECTED_FILTER_NAMES = {"postedWithin": "posted_within", "workFromHome": "remote", "jobTypes": "job_type",
                         "companyTypes": "company_type", "salary": "salary_min", "skills": "skill"}
POSTED_WITHIN_VALUES = {"1": "1_day", "3": "3_days", "7": "7_days", "14": "14_days"}


def _new_engine_applied(state):
    """The new engine's categorization / selectedFilters -> public words."""
    cat = as_dict(g(state, "searchResults", "categorization"))
    sel = as_dict(g(state, "searchResults", "selectedFilters"))
    out = {}
    contract = text(sel.get("contractTypes") or cat.get("contractTypes"))
    work = text(sel.get("worktypes") or cat.get("worktypes"))
    if contract and contract in NEW_CONTRACT_TYPES:
        out["job_type"] = NEW_CONTRACT_TYPES[contract]
    elif work and work in NEW_WORK_TYPES:
        out["job_type"] = NEW_WORK_TYPES[work]
    salary = to_int(sel.get("unifiedSalary") or cat.get("unifiedSalary"))
    if salary:
        out["salary_min"] = salary
    skills = text(sel.get("skills") or cat.get("skills"))
    if skills:
        out["skill"] = [v for v in skills.split(",") if v]
    return out


def applied_filters(state):
    """searchResults.selectedFilters (the UK board's record of the filters in
    force) -> {public param: value} in the API's own words."""
    if is_new_engine(state):
        return _new_engine_applied(state)
    out = {}
    for key, value in as_dict(g(state, "searchResults", "selectedFilters")).items():
        name = SELECTED_FILTER_NAMES.get(key)
        if not name or value in (None, "", [], {}):
            continue
        raw = str(value)
        if name == "posted_within":
            out[name] = POSTED_WITHIN_VALUES.get(raw, raw)
        elif name == "salary_min":
            out[name] = to_int(raw)
        elif name == "skill":
            out[name] = [v for v in raw.split(",") if v]
        else:
            out[name] = _words(name, raw)
    return out


def search_results(state):
    """app-unifiedResultlist -> {search, jobs, counts, related_searches,
    related_skills, breadcrumbs, pagination} with UK filter words."""
    out = strip_site(P.search_results(state, SITE))
    if is_new_engine(state):
        applied = applied_filters(state)
    else:
        applied = {k: _words(k, v) for k, v in as_dict(g(out, "search", "filters")).items() if k != "company"}
        applied.update(applied_filters(state))
    out["search"]["filters"] = applied
    out["search"]["radius_unit"] = "miles"
    return out


def is_new_engine(state):
    """True when the result list came from Totaljobs' newer StepStone engine
    (its own facet set and URL params; the UK params are ignored there)."""
    kinds = {as_dict(b).get("type") for b in as_list(g(state, "searchResults", "filters"))}
    return bool(kinds & NEW_ENGINE_MARKERS)


def _block_options(block, mapping=None, ints=False):
    out = []
    for child in as_list(as_dict(block).get("children")):
        child = as_dict(child)
        option_id, label = text(child.get("id")), text(child.get("text"))
        if option_id is None or (label is None and not ints):
            continue
        if mapping is not None:
            if option_id not in mapping:
                continue
            value = mapping[option_id]
        else:
            value = to_int(option_id) if ints else option_id
        out.append({"value": value, "label": label, "count": to_int(child.get("count")),
                    "is_selected": bool(child.get("selected"))})
    return out


def _new_engine_facets(state):
    """The new engine's facet blocks -> {public name: (label, is_active, options)}."""
    blocks = {as_dict(b).get("type"): as_dict(b) for b in as_list(g(state, "searchResults", "filters"))}
    labels = as_dict(g(state, "labels", "filters", "categories"))
    out = {}

    def put(name, kind, options):
        if options:
            block = blocks.get(kind, {})
            out[name] = (text(labels.get(kind)), bool(block.get("active")), options)
    put("posted_within", "age", _block_options(blocks.get("age"), NEW_AGE_VALUES))
    put("remote", "workPolicy", _block_options(blocks.get("workPolicy"), NEW_WORK_POLICIES))
    job_types = _block_options(blocks.get("contractTypes"), NEW_CONTRACT_TYPES) + \
        _block_options(blocks.get("worktypes"), NEW_WORK_TYPES)
    put("job_type", "contractTypes", job_types)
    put("salary_min", "unifiedSalary", _block_options(blocks.get("unifiedSalary"), ints=True))
    put("skill", "skills", _block_options(blocks.get("skills")))
    return out


def all_facets(state):
    """Every facet mapped to public words -> {name: [options]}, including the
    informational ones (company_type, the new engine's 30-day age, hybrid)."""
    if is_new_engine(state):
        return {name: options for name, (_, _, options) in _new_engine_facets(state).items()}
    out = {}
    for facet in P.filters(state, SITE):
        name = facet.get("name")
        out[name] = [{**o, "value": _words(name, o.get("value"))} for o in as_list(facet.get("options"))]
    return out


def filters(state):
    """The search facets with counts -> [{name, label, param, is_active,
    options:[{value, label, count, is_selected}]}] — only facets whose
    options the same-named search param accepts: posted_within (UK engine),
    remote, job_type, salary_min (new engine), skill ids."""
    out = []
    if is_new_engine(state):
        for name, (label, active, options) in _new_engine_facets(state).items():
            if name == "posted_within":
                continue                 # the new engine cannot filter by posting date
            if name == "remote":
                options = [o for o in options if o["value"] in ("full", "none")]
            if options:
                out.append({"name": name, "label": label, "param": name, "is_active": active, "options": options})
        return out
    for facet in P.filters(state, SITE):
        name = facet.get("name")
        if name not in PUBLIC_FILTERS:
            continue
        options = [{**o, "value": _words(name, o.get("value"))} for o in as_list(facet.get("options"))]
        out.append({**facet, "options": options})
    return out


def popular_locations(state):
    """locationFacet (else popularLocations) -> [{id, name, count, link}]:
    the places near the search with live job counts."""
    blocks = {as_dict(b).get("type"): as_dict(b) for b in as_list(g(state, "searchResults", "filters"))}
    block = blocks.get("locationFacet") or blocks.get("popularLocations") or {}
    out, seen = [], set()
    for group in as_list(block.get("children")):
        group = as_dict(group)
        children = as_list(group.get("children")) or ([group] if group.get("link") else [])
        for child in children:
            child = as_dict(child)
            name = text(child.get("text"))
            if not name or name in seen:
                continue
            seen.add(name)
            out.append({"id": to_int(child.get("id")), "name": name, "count": to_int(child.get("count")),
                        "link": clean_link(child.get("link"), SITE) if child.get("link") else None})
    return out


def stats(state):
    """A result list -> market counts for the query: the totals plus every
    facet's breakdown (posting age, job type, company type, remote, top
    skills) and the busiest nearby locations."""
    out = search_results(state)
    facets = all_facets(state)

    def rows(name):
        return [{"value": o.get("value"), "label": o.get("label"), "count": o.get("count")} for o in facets.get(name, [])]
    return {
        "search": out["search"],
        "total_count": g(out, "counts", "total"),
        "counts": out["counts"],
        "by_posted_within": rows("posted_within"),
        "by_job_type": rows("job_type"),
        "by_company_type": rows("company_type"),
        "by_remote": rows("remote"),
        "top_skills": [{"id": to_int(o.get("value")), "name": o.get("label"), "count": o.get("count")} for o in facets.get("skill", [])],
        "popular_locations": popular_locations(state),
        "related_searches": out["related_searches"],
    }


# ---- job / company pages -------------------------------------------------------------------------

def job_details(html, job_id=None):
    """A job page -> the full job object (None when the page carries no job)."""
    out = P.job_details(html, SITE, job_id)
    return strip_site(out) if out else None


def similar_jobs(html):
    return strip_site(P.similar_jobs(extract_app(html, "RecommenderWidget_listing_list"), SITE))


def company_details(html, company_id=None):
    """A company jobs page -> the company profile: identity, logo, passport
    fields when the employer has one, live job count, the type the board
    files it under (direct employer / agency), and where / what kind / which
    skills its jobs are."""
    out = P.company_details(html, SITE, company_id)
    if not out:
        return None
    out = strip_site(out)
    for key in ("job_locations", "job_disciplines", "job_contract_types"):
        out.pop(key, None)
    state = extract_app(html, "app-unifiedResultlist")
    facets = all_facets(state) if state else {}
    company_types = [o for o in facets.get("company_type", []) if o.get("count")]
    out["type"] = max(company_types, key=lambda o: o.get("count") or 0)["value"] if company_types else None
    out["job_types"] = [{"type": o.get("value"), "label": o.get("label"), "count": o.get("count")} for o in facets.get("job_type", [])]
    out["job_skills"] = [{"id": to_int(o.get("value")), "name": o.get("label"), "count": o.get("count")} for o in facets.get("skill", [])]
    out["job_locations"] = popular_locations(state) if state else []
    out["remote_jobs_count"] = next((o.get("count") for o in facets.get("remote", []) if o.get("value") == "full"), None)
    return out


def autosuggest(payload):
    """/searchbar/autosuggest/suggest -> [{title, type, frequency}] (the UK
    board suggests job titles only, with how many live postings carry each)."""
    return [{"title": s["title"], "type": s.get("type"), "frequency": s.get("frequency")} for s in P.autosuggest(payload)]


# ---- advice library (WordPress HTML) ------------------------------------------------------------------

_CARD_RE = re.compile(r'<article class="card(?P<classes>[^"]*)">(?P<body>.*?)</article>', re.S)
_POST_ID_RE = re.compile(r"\bpost-(\d+)\b")
_CATEGORY_RE = re.compile(r"\bcategory-([a-z0-9\-]+)")
_HREF_RE = re.compile(r'<a class="content" href="([^"]+)"')
_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"')
_HEADING_RE = re.compile(r'<h3 class="article__heading">(.*?)</h3>', re.S)
_BACK_RE = re.compile(r'<div class="article__back">(.*?)(?:<div class="article__meta">|</a>)', re.S)
_EXCERPT_RE = re.compile(r'<h3 class="article__heading">.*?</h3>(.*?)</div>', re.S)
_READ_TIME_RE = re.compile(r"(\d+)\s*min read")
_TIME_RE = re.compile(r'<time class="published" datetime="([^"]+)"')
_META_RE = r'<meta (?:property|name)="{}" content="([^"]*)"'
_CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_BODY_CLASS_RE = re.compile(r'<body[^>]+class="([^"]*)"')
_PAGE_NUMBERS_RE = re.compile(r'class="page-numbers(?P<current> current)?"[^>]*>(?P<n>\d+)<')
_H2_SPLIT_RE = re.compile(r"<h2\b[^>]*>", re.I)
_H2_RE = re.compile(r'<h2\b([^>]*)>(.*?)</h2>', re.S | re.I)
_ID_ATTR_RE = re.compile(r'\bid="([^"]+)"')
_FAQ_RE = re.compile(r'class="faq-question">\s*<h3[^>]*>(.*?)</h3>(.*?)</div>\s*</div>', re.S)
_FAQ_ANSWER_RE = re.compile(r'class="faq-a"[^>]*>(.*?)</p>', re.S)
_TOPIC_TAG_RE = re.compile(r'<li class="related-topics-theme-tags-list-item">\s*<h3>\s*<a href="([^"]+)">\s*(.*?)\s*</a>', re.S)
_CONTRIBUTOR_RE = re.compile(r'class="piece-contributor">(.*?)<div class="wrap">', re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _meta(html, name):
    match = re.search(_META_RE.format(re.escape(name)), html)
    return text(unescape(match.group(1))) if match else None


def _plain(fragment):
    return text(unescape(_TAG_RE.sub(" ", fragment or "")))


def advice_slug(url):
    url = (url or "").split("?")[0].split("#")[0].rstrip("/")
    return url.rsplit("/", 1)[-1] if "/advice/" in url else None


def _div_block(html, start):
    """The HTML from the <div at `start` to its matching </div>."""
    depth = 0
    for match in re.finditer(r"<div\b|</div>", html[start:]):
        depth += 1 if match.group(0).startswith("<div") else -1
        if depth == 0:
            return html[start:start + match.end()]
    return html[start:]


def _block(html, class_name):
    match = re.search(r'<div class="[^"]*\b%s\b[^"]*"' % re.escape(class_name), html)
    return _div_block(html, match.start()) if match else None


def advice_card(match):
    """One <article class="card …"> -> an article summary (None for a topic
    card, which has no post id)."""
    classes, body = match.group("classes"), match.group("body")
    post = _POST_ID_RE.search(classes)
    href = _HREF_RE.search(body)
    heading = _HEADING_RE.search(body)
    back = _BACK_RE.search(body) or _EXCERPT_RE.search(body)
    read = _READ_TIME_RE.search(body)
    when = _TIME_RE.search(body)
    image = _IMG_RE.search(body)
    link = unescape(href.group(1)) if href else None
    card = {
        "id": to_int(post.group(1)) if post else None,
        "title": _plain(heading.group(1)) if heading else None,
        "slug": advice_slug(link),
        "link": link,
        "summary": html_to_text(back.group(1)) if back else None,
        "image_link": unescape(image.group(1)) if image else None,
        "read_time_minutes": to_int(read.group(1)) if read else None,
        "published_at": iso_datetime(when.group(1)) if when else None,
        "topics": _CATEGORY_RE.findall(classes),
    }
    if not card["title"] and not card["link"]:
        return None
    return card


def _cards(fragment):
    return [c for c in (advice_card(m) for m in _CARD_RE.finditer(fragment or "")) if c]


def _topic_cards(fragment):
    """Topic cards (no post id) -> [{name, slug, link, description}]."""
    out = []
    for card in _cards(fragment):
        if card["id"] is None:
            out.append({"name": card["title"], "slug": card["slug"], "link": card["link"], "description": card["summary"]})
    return out


def _pagination(html, page, per_page, count):
    numbers = [(to_int(m.group("n")), bool(m.group("current"))) for m in _PAGE_NUMBERS_RE.finditer(html)]
    total_pages = max((n for n, _ in numbers if n), default=None)
    current = next((n for n, cur in numbers if cur), None) or page
    return {"page": current, "items_per_page": per_page, "total_count": None, "total_pages": total_pages}


def advice_listing(html, page=1):
    """A topic hub (/advice/<topic>?page=N) or the advice search page
    (/advice/?s=…) -> {topic, articles, subtopics, related_topics,
    pagination}. Articles come from the page's "All in …" / search-results
    block; the hub's "Explore" cards are the subtopics; "Popular topics" /
    parent-topic cards the related topics."""
    title = _H1_RE.search(html)
    canonical = _CANONICAL_RE.search(html)
    standfirst = _block(html, "standfirst")
    listing = _block(html, "all-pieces") or _block(html, "card-search")
    articles = _cards(listing) if listing else []
    explore = None
    for match in re.finditer(r'<div class="topic-content-builder">', html):
        block = _div_block(html, match.start())
        if re.search(r"<h2[^>]*>\s*Explore", block):
            explore = block
            break
    related = []
    for class_name in ("popular-in--parent-topics", "popular-in--topics"):
        related.extend(_topic_cards(_block(html, class_name)))
    seen, related_topics = set(), []
    for topic in related:
        if topic["link"] and topic["link"] not in seen:
            seen.add(topic["link"])
            related_topics.append(topic)
    link = unescape(canonical.group(1)) if canonical else None
    return {
        "topic": {
            "name": _plain(title.group(1)) if title else None,
            "slug": advice_slug(link),
            "link": link,
            "description": html_to_text(standfirst) if standfirst else _meta(html, "description"),
            "image_link": _meta(html, "og:image"),
        },
        "articles": articles,
        "subtopics": _topic_cards(explore) if explore else [],
        "related_topics": related_topics,
        "pagination": _pagination(html, page, len(articles) or None, None),
    }


def _sections(body_html):
    """body_text HTML split on <h2> -> [{id, title, text, html}]; the text
    before the first heading is the introduction."""
    out = []
    starts = [m.start() for m in _H2_SPLIT_RE.finditer(body_html)]
    chunks = [body_html[:starts[0]] if starts else body_html] + [body_html[s:e] for s, e in zip(starts, starts[1:] + [len(body_html)])]
    for chunk in chunks:
        heading = _H2_RE.match(chunk)
        title = _plain(heading.group(2)) if heading else None
        section_id = (_ID_ATTR_RE.search(heading.group(1)) or [None, None])[1] if heading else None
        content = chunk[heading.end():] if heading else chunk
        body = html_to_text(content)
        if not body and not title:
            continue
        out.append({"id": section_id, "title": title or ("Introduction" if not heading else None),
                    "text": body, "html": content.strip() or None})
    return out


def advice_article(html):
    """An advice article (/advice/<slug>) -> {id, title, slug, link, standfirst,
    published_at, updated_at, image_link, author, read_time_minutes, topics,
    table_of_contents, sections, faqs, content, related_articles}; None when
    the page is not an article (no body_text)."""
    blocks = []
    for match in re.finditer(r'<div class="body_text">', html):
        block = _div_block(html, match.start())
        blocks.append(block[len('<div class="body_text">'):-len("</div>")] if block.endswith("</div>") else block)
    if not blocks:
        return None
    body_inner = "\n".join(blocks)
    title = _H1_RE.search(html)
    canonical = _CANONICAL_RE.search(html)
    body_class = _BODY_CLASS_RE.search(html)
    post_id = re.search(r"\bpostid-(\d+)", body_class.group(1)) if body_class else None
    standfirst = _block(html, "piece-standfirst")
    contributor = _CONTRIBUTOR_RE.search(html)
    author = None
    if contributor:
        href = re.search(r'href="([^"]+)"', contributor.group(1))
        image = _IMG_RE.search(contributor.group(1))
        name = _plain(re.sub(r"<img[^>]*>", "", contributor.group(1)))
        if name or href:
            author = {"name": name, "link": unescape(href.group(1)) if href else None,
                      "image_link": unescape(image.group(1)) if image else None}
    read = re.search(r'piece-read-time">\s*<span>(\d+)\s*min read', html)
    sections = _sections(body_inner)
    link = unescape(canonical.group(1)) if canonical else _meta(html, "og:url")
    self_link = (link or "").rstrip("/")
    related = [c for c in _cards(html) if (c["link"] or "").rstrip("/") != self_link]
    seen, related_articles = set(), []
    for card in related:
        if card["link"] not in seen:
            seen.add(card["link"])
            related_articles.append(card)
    return {
        "id": to_int(post_id.group(1)) if post_id else None,
        "title": _plain(title.group(1)) if title else _meta(html, "og:title"),
        "slug": advice_slug(link),
        "link": link,
        "standfirst": html_to_text(standfirst) if standfirst else _meta(html, "description"),
        "published_at": iso_datetime(_meta(html, "article:published_time")),
        "updated_at": iso_datetime(_meta(html, "article:modified_time")),
        "image_link": _meta(html, "og:image"),
        "author": author,
        "read_time_minutes": to_int(read.group(1)) if read else None,
        "topics": [{"name": _plain(name), "slug": advice_slug(unescape(href)), "link": unescape(href)}
                   for href, name in _TOPIC_TAG_RE.findall(html)],
        "table_of_contents": [{"id": s["id"], "title": s["title"]} for s in sections if s.get("id")],
        "sections": sections,
        "faqs": [{"question": _plain(q), "answer": html_to_text((_FAQ_ANSWER_RE.search(a) or [None, a])[1])}
                 for q, a in _FAQ_RE.findall(body_inner)],
        "content": {"text": html_to_text(body_inner), "html": body_inner.strip() or None},
        "related_articles": related_articles,
    }


__all__ = ["extract_app", "clean_link", "strip_site", "search_results", "applied_filters", "is_new_engine", "all_facets", "filters", "popular_locations", "stats",
           "job_details", "similar_jobs", "company_details", "autosuggest", "advice_listing", "advice_article",
           "advice_slug", "site_link"]
