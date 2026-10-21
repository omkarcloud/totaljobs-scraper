"""Marshmallow request schemas for every /totaljobs/* route.

Generic fields live in the shared top-level schema_fields.py; this module
adds the Totaljobs resolvers (refs.py). Every schema's load() output is the
kwargs dict its endpoint function takes.

ONE param per input (tripadvisor QueryOrLinkField convention, never a
sibling `url`/`id` pair): `job` takes a job id OR a job link; `company` a
company id, 'slug-id', a company name or a company link; `link` a search or
company listing link; `article` / `topic` an advice slug or link.

Filter values: `posted_within`, `remote` and `job_type` are words;
`skill` takes the ids /totaljobs/jobs/filters lists for the same search.
There is no company-type filter: Totaljobs' own one changes nothing (its
counts are in /jobs/stats and /companies/details).
"""
import re

from marshmallow import ValidationError, fields, validate, validates_schema

from schema_fields import BaseSchema, ChoiceField, CommaListField, PageField, PositiveInt, QueryField, RefField, StrippedString
from totaljobs import refs

MAX_BATCH = 10
MAX_PAGE = 200          # the site stops at 5,000 results = 200 pages of 25
MAX_ADVICE_PAGE = 50
_ID_RE = re.compile(r"^[A-Za-z0-9_]{1,24}$")


class JobField(RefField):
    resolver = staticmethod(refs.resolve_job)


class CompanyField(RefField):
    resolver = staticmethod(refs.resolve_company)


class ListingLinkField(RefField):
    resolver = staticmethod(refs.resolve_listing)


class ArticleField(RefField):
    resolver = staticmethod(refs.resolve_article)


class TopicField(RefField):
    resolver = staticmethod(refs.resolve_topic)

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("load_default", "job-descriptions")
        super().__init__(**kwargs)


class JobListField(fields.Field):
    """'108167578, https://www.totaljobs.com/job/…-job108061802' -> resolved jobs (1..MAX_BATCH)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        try:
            return refs.resolve_jobs(value, MAX_BATCH)
        except ValueError as e:
            raise ValidationError(str(e))


class IdListField(CommaListField):
    """Filter option ids from /totaljobs/jobs/filters ('659280,671433')."""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_items", 10)
        super().__init__(upper=False, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        items = super()._deserialize(value, attr, data, **kwargs)
        for item in items or []:
            if not _ID_RE.match(item):
                raise ValidationError(f"'{item}' is not a filter id (see /totaljobs/jobs/filters).")
        return items


# ---- jobs ----------------------------------------------------------------------------------------

class _JobFilters(BaseSchema):
    radius = fields.Integer(load_default=None, strict=False, validate=validate.Range(min=0, max=200))
    posted_within = ChoiceField(["1_day", "3_days", "7_days", "14_days"])
    remote = ChoiceField(["full", "none"])
    job_type = ChoiceField(["permanent", "contract", "temporary", "part_time", "work_from_home"])
    salary_min = PositiveInt(max_value=10_000_000)
    skill = IdListField()


class _KeywordLocation(_JobFilters):
    keyword = StrippedString(required=False, load_default=None, validate=validate.Length(max=200))
    location = StrippedString(required=False, load_default=None, validate=validate.Length(max=150))


class _NeedsQuery(_KeywordLocation):
    @validates_schema
    def _needs_a_query(self, data, **kwargs):
        if not data.get("keyword") and not data.get("location"):
            raise ValidationError("Give a keyword, a location, or both.", "keyword")


class JobSearchSchema(_NeedsQuery):
    sort = ChoiceField(["relevance", "date"], load_default="relevance")
    page = PageField(max_page=MAX_PAGE)


class JobFiltersSchema(_NeedsQuery):
    pass


class JobStatsSchema(_KeywordLocation):
    """Keyword and location both optional: nothing = the whole UK board."""


class JobSchema(BaseSchema):
    job = JobField()


class JobBatchSchema(BaseSchema):
    jobs = JobListField()


class ListingSchema(BaseSchema):
    link = ListingLinkField()
    page = PageField(max_page=MAX_PAGE)


# ---- companies ---------------------------------------------------------------------------------

class CompanySchema(BaseSchema):
    company = CompanyField()


class CompanyJobsSchema(_JobFilters):
    company = CompanyField()
    sort = ChoiceField(["relevance", "date"], load_default="relevance")
    page = PageField(max_page=MAX_PAGE)


# ---- lookups -------------------------------------------------------------------------------------

class AutocompleteSchema(BaseSchema):
    query = QueryField(max_length=100)
    limit = fields.Integer(load_default=10, strict=False, validate=validate.Range(min=1, max=20))


class PopularSchema(BaseSchema):
    keyword = StrippedString(required=False, load_default=None, validate=validate.Length(max=200))
    location = StrippedString(required=False, load_default=None, validate=validate.Length(max=150))
    radius = fields.Integer(load_default=None, strict=False, validate=validate.Range(min=0, max=200))


# ---- advice --------------------------------------------------------------------------------------

class AdviceArticlesSchema(BaseSchema):
    topic = TopicField()
    page = PageField(max_page=MAX_ADVICE_PAGE)


class AdviceArticleSchema(BaseSchema):
    article = ArticleField()


class AdviceSearchSchema(BaseSchema):
    query = QueryField(max_length=100)
    page = PageField(max_page=MAX_ADVICE_PAGE)
