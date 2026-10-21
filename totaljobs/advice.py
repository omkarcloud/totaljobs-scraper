"""/totaljobs/advice/* — the career-advice library at totaljobs.com/advice/:
topic hubs (job-descriptions and its ~20 sector sub-hubs with ~100 role
profiles; cvs, interviews, pay-and-benefits, …), one article in full, and
the library's own search. Server-rendered WordPress HTML; the wp-json REST
is Akamai-blocked, the HTML is not (fetch.py).
"""
from totaljobs import fetch
from totaljobs import parsers as P

SEARCH_PER_PAGE = 10
DEFAULT_TOPIC = "job-descriptions"


def articles(topic=DEFAULT_TOPIC, page=1):
    """One page of a topic hub: its articles (role profiles for the
    job-descriptions hubs), subtopics and related topics."""
    params = {"page": page} if page > 1 else None
    resp = fetch.page(f"/advice/{topic}", params, label=f"advice topic {topic!r}")
    out = P.advice_listing(resp.text, page)
    if not out["articles"] and not out["subtopics"] and page == 1:
        if "/advice/" not in resp.url or not out["topic"]["name"]:
            raise fetch.NotFound(f"Totaljobs advice has no topic '{topic}'")
    if page > 1 and out["pagination"]["page"] != page and not out["articles"]:
        raise fetch.NotFound(f"Topic '{topic}' has no page {page}")
    if out["pagination"]["total_pages"] is None and out["articles"]:
        # a one-page hub prints no page numbers; paginate would report 0 pages
        out["pagination"]["total_pages"] = out["pagination"]["page"]
    return out


def details(article):
    """One advice article by slug or link: standfirst, author, dates, read
    time, topics, table of contents, the sections (text + HTML), FAQs and
    the related articles."""
    resp = fetch.page(f"/advice/{article}", label=f"advice article {article!r}")
    out = P.advice_article(resp.text)
    if not out:
        if P.advice_listing(resp.text)["articles"]:
            raise fetch.BadRequest(f"'{article}' is a topic hub, not an article — use /totaljobs/advice/articles?topic={article}")
        raise fetch.NotFound(f"Totaljobs advice has no article '{article}'")
    return out


def search(query, page=1):
    """Search the advice library (10 per page; /advice/?s=…&_paged=N). The
    site does not say how many pages there are: a full page means there may
    be another."""
    params = {"s": query, "_paged": page if page > 1 else None}
    resp = fetch.page("/advice/", params, label=f"advice search {query!r}" + (f" page {page}" if page > 1 else ""))
    out = P.advice_listing(resp.text, page)
    articles = out["articles"]
    pagination = {"page": page, "items_per_page": SEARCH_PER_PAGE, "total_count": None,
                  "total_pages": page + 1 if len(articles) >= SEARCH_PER_PAGE else page}
    return {"query": query, "articles": articles, "related_topics": out["related_topics"], "pagination": pagination}
