"""Totaljobs transport = the StepStone fetcher (stepstone/fetch.py) pinned to
the totaljobs.com board row.

Plain curl_cffi (Chrome TLS impersonation) is the only path in normal
operation: every search / company page embeds its result list as
window.__PRELOADED_STATE__["app-unifiedResultlist"], every job page its
JobAdContent state plus a JSON-LD JobPosting, autosuggest is a JSON GET and
the advice library is server-rendered WordPress HTML.

Anti-bot (validated 2026-10-19 from an office line, a datacenter IP and a UK
residential proxy exit): Akamai Bot Manager refuses datacenter /
office IPs on EVERY request (403 "Access Denied") — search, job, company,
autosuggest and advice alike — while a Chrome-impersonated session on a UK
residential exit gets 200 on all of them (search 2.2 s, job 1.0 s, company
1.2 s, autosuggest 0.6 s, advice 3.1 s). Some URLs (the bare /jobs page, the
advice pages) answer a fresh session with a 2.5 KB Akamai *interstitial*
(proof-of-work POSTed to /_sec/verify); stepstone.fetch clears it in plain
HTTP, one extra round trip. A refused call is retried on a fresh exit
(config.STEPSTONE_MAX_ATTEMPTS) and only when every exit is refused does one
headful patchright Chrome load the page (config.STEPSTONE_BROWSER_FALLBACK)
— never triggered during the build. Blocked everywhere (3 exits + browser):
the legacy /JobSeeking/Browse_*.html, /CompanySearch, the /jobs-at/ root and
the advice site's wp-json REST — none of which a route needs.

Errors are the stepstone ones re-raised with "Totaljobs" in the message
(route_glue maps NotFound -> 404, BadRequest -> 400, Blocked / UpstreamError
-> 502).
"""
from stepstone import fetch as _fetch
from stepstone import sites as S
from stepstone.fetch import (StepstoneBadRequest as BadRequest, StepstoneBlocked as Blocked,
                             StepstoneNotFound as NotFound, StepstoneUpstreamError as UpstreamError,
                             run_parallel)

SITE = S.site("totaljobs")
HOST = SITE["host"]
SITE_ID = SITE["site_id"]

__all__ = ["SITE", "HOST", "SITE_ID", "page", "get_json", "link", "run_parallel",
           "BadRequest", "Blocked", "NotFound", "UpstreamError"]


def _rebrand(exc):
    """The same exception with the StepStone wording swapped for Totaljobs."""
    message = str(exc).replace("StepStone", "Totaljobs").replace("stepstone", "totaljobs")
    if isinstance(exc, Blocked):
        return Blocked(message, status=getattr(exc, "status", None))
    return type(exc)(message)


def page(path, params=None, label=None):
    """GET a totaljobs.com page -> Response(text, final url, status)."""
    try:
        return _fetch.page(SITE, path, params, label=label or f"{HOST}{path}")
    except (NotFound, BadRequest, UpstreamError) as e:
        raise _rebrand(e) from None


def get_json(path, params=None, label=None):
    """GET a totaljobs.com JSON endpoint -> parsed body."""
    try:
        return _fetch.get_json(SITE, path, params, label=label or f"{HOST}{path}")
    except (NotFound, BadRequest, UpstreamError) as e:
        raise _rebrand(e) from None


def link(path):
    return S.link(SITE, path)
