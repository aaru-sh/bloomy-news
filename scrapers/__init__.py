"""Scraper package: HTTP, RSS, keyword helpers, and 8 source scrapers.

All public symbols are re-exported from submodules for callers that
prefer `from scrapers import fetch_url, scrape_arxiv, ...` over
`from scrapers._http import fetch_url`. The individual modules stay
importable for tests that want to patch internals.
"""
from ._http import Article, ArticleList, SOURCE_NAMES, fetch_json, fetch_url
from ._keywords import (
    CATEGORY_KEYWORDS,
    STOPWORDS,
    SUBCATEGORY_KEYWORDS,
    _tokenize,
    _keyword_tokens,
    _filter_keywords,
    _FILTERED_CATEGORY_KEYWORDS,
    _FILTERED_SUBCATEGORY_KEYWORDS,
)
from ._rss import parse_rss, _parse_rss_regex
from .arxiv import scrape_arxiv
from .cybersec import scrape_cybersec
from .finance import scrape_finance
from .github import scrape_github
from .google_news import scrape_google_news, resolve_google_news_redirect
from .markets import scrape_markets
from .newsapi import scrape_newsapi
from .tech import scrape_tech

__all__ = [
    "Article",
    "ArticleList",
    "SOURCE_NAMES",
    "fetch_url",
    "fetch_json",
    "parse_rss",
    "_parse_rss_regex",
    "CATEGORY_KEYWORDS",
    "SUBCATEGORY_KEYWORDS",
    "STOPWORDS",
    "_tokenize",
    "_keyword_tokens",
    "_filter_keywords",
    "_FILTERED_CATEGORY_KEYWORDS",
    "_FILTERED_SUBCATEGORY_KEYWORDS",
    "scrape_arxiv",
    "scrape_github",
    "scrape_newsapi",
    "scrape_cybersec",
    "scrape_tech",
    "scrape_finance",
    "scrape_google_news",
    "scrape_markets",
    "resolve_google_news_redirect",
]
