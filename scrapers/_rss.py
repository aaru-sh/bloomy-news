"""RSS / Atom parsing.

Primary path uses feedparser (handles RSS 2.0, RSS 1.0, Atom, all
date formats, CDATA, HTML entities, dc:creator, and inline HTML
in summaries). The legacy regex parser is kept as `_parse_rss_regex`
and called via `logger.warning` if feedparser raises an unexpected
exception - we never want a single malformed feed to drop the whole
scrape.

Both paths return up to 20 articles per feed, each shaped as
{title, url, summary, source, source_key, published, author}.
"""
import html
import logging
import re
from typing import Any, List

from ._http import SOURCE_NAMES, Article, ArticleList

logger = logging.getLogger(__name__)


def parse_rss(xml_text: str, source_key: str) -> ArticleList:
    """Parse an RSS or Atom feed into the canonical article dict shape.

    Primary path uses feedparser; the legacy regex parser is the
    fallback for pathological inputs that crash feedparser.
    """
    try:
        import feedparser
        feed = feedparser.parse(xml_text)
        articles: ArticleList = []
        source_name = SOURCE_NAMES.get(source_key, source_key)
        for entry in feed.entries[:20]:
            title = (getattr(entry, "title", "") or "").strip()
            url = (getattr(entry, "link", "") or "").strip()
            if not title or not url:
                continue
            # Summary: feedparser normalizes description -> summary.
            # Atom entries use .summary; some RSS feeds only have .description.
            summary = (getattr(entry, "summary", "")
                       or getattr(entry, "description", "")
                       or "")
            # Strip any HTML left in the summary. feedparser does not
            # always do this; some feeds include full <p> markup.
            if summary and "<" in summary:
                summary = re.sub(r"<[^>]+>", "", summary).strip()
            # Author: feedparser maps dc:creator to .author; some feeds
            # put a list in .authors with dict payloads.
            author = (getattr(entry, "author", "") or "").strip()
            if not author and getattr(entry, "authors", None):
                first = entry.authors[0]
                if isinstance(first, dict):
                    author = first.get("name", "")
                else:
                    author = str(first)
            # Published: feedparser leaves the raw string in .published
            # and parses to a 9-tuple in .published_parsed. We keep the
            # raw string for backward compat with downstream code.
            published = (getattr(entry, "published", "")
                         or getattr(entry, "updated", "")
                         or "")
            articles.append({
                "title": title,
                "url": url,
                "summary": summary[:600] if summary else "",
                "source": source_name,
                "source_key": source_key,
                "published": published,
                "author": author,
            })
        return articles
    except Exception as exc:
        logger.warning(
            "feedparser failed for source=%s (%s); falling back to regex",
            source_key, exc,
        )
        return _parse_rss_regex(xml_text, source_key)


def _parse_rss_regex(xml_text: str, source_key: str) -> ArticleList:
    """Regex-based RSS/Atom parser (legacy fallback). Used only when
    feedparser raises an unexpected exception. Kept for parity with
    the v1.1.x behavior locked in by tests/test_scraper_*.py."""
    articles: ArticleList = []
    source_name = SOURCE_NAMES.get(source_key, source_key)

    items = re.findall(r'<item>(.*?)</item>', xml_text, re.DOTALL)
    if not items:
        items = re.findall(r'<entry>(.*?)</entry>', xml_text, re.DOTALL)

    for item in items[:20]:
        title = url = summary = published = ""
        author = ""

        t = re.search(r'<title[^>]*>(.*?)</title>', item, re.DOTALL)
        if t:
            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', t.group(1)).strip()
            title = re.sub(r'<[^>]+>', '', title).strip()

        u = re.search(r'<link[^>]*>(.*?)</link>', item, re.DOTALL)
        if not u:
            u = re.search(r'<link[^>]*href="([^"]*)"', item)
        if u:
            url = re.sub(r'<[^>]+>', '', u.group(1)).strip()

        for tag in ['description', 'summary', 'content', 'content:encoded']:
            s = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', item, re.DOTALL)
            if s:
                summary = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', s.group(1)).strip()
                summary = re.sub(r'<[^>]+>', '', summary).strip()
                break

        for tag in ['pubDate', 'published', 'updated', 'dc:date', 'atom:updated']:
            p = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', item, re.DOTALL)
            if p:
                published = p.group(1).strip()
                break

        a = re.search(r'<author[^>]*>(.*?)</author>', item, re.DOTALL)
        if a:
            author = re.sub(r'<[^>]+>', '', a.group(1)).strip()

        title = html.unescape(title)
        url = html.unescape(url)
        summary = html.unescape(summary)
        summary = re.sub(r'<[^>]+>', '', summary)

        if title and url:
            articles.append({
                "title": title,
                "url": url,
                "summary": summary[:600] if summary else "",
                "source": source_name,
                "source_key": source_key,
                "published": published,
                "author": author,
            })

    return articles
