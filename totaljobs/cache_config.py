"""Cache TTL per /totaljobs/* endpoint (cache.py, keyed on the validated
params — marshmallow fills the defaults, so an omitted param and its default
share a row).

Result lists churn hourly (new postings, expiries); a single job changes
rarely once posted; company pages move daily at most; autosuggest
frequencies and the advice library drift slowly."""
from datetime import timedelta

SEARCH_CACHE = timedelta(hours=1)
FILTERS_CACHE = timedelta(hours=1)
STATS_CACHE = timedelta(hours=1)
LISTING_CACHE = timedelta(hours=1)
JOB_CACHE = timedelta(hours=6)
SIMILAR_CACHE = timedelta(hours=6)
COMPANY_CACHE = timedelta(days=1)
COMPANY_JOBS_CACHE = timedelta(hours=1)
POPULAR_CACHE = timedelta(days=1)
AUTOCOMPLETE_CACHE = timedelta(days=7)
ADVICE_LIST_CACHE = timedelta(days=1)
ADVICE_ARTICLE_CACHE = timedelta(days=7)
ADVICE_SEARCH_CACHE = timedelta(days=1)
