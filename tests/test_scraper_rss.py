"""Scraper correctness tests for the RSS-based scrapers in news_tool.py
and `parse_rss()` edge cases. Covers:

  - scrape_cybersec()      (3 RSS feeds)
  - scrape_tech()          (3 RSS feeds)
  - scrape_google_news()   (3 RSS feeds + redirect resolution)
  - scrape_markets()       (2 RSS feeds)
  - parse_rss() edge cases (Atom <entry>, HTML entities, missing fields)

All tests use unittest.mock.patch on news_tool.fetch_url to avoid
real HTTP calls. They lock in CURRENT behavior so a future feedparser
swap (v1.2.0, separate worktree) is verifiable by re-running the
same tests.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "dashboard"))


def _rss_item(title, link, description, pubdate="Mon, 05 Jun 2026 12:00:00 GMT",
              author="Author Name"):
    return f"""<item>
<title>{title}</title>
<link>{link}</link>
<description>{description}</description>
<author>{author}</author>
<pubDate>{pubdate}</pubDate>
</item>"""


def _rss_doc(items, channel_title="Test Channel"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>{channel_title}</title>
<description>Test feed</description>
{items}
</channel></rss>"""


def _atom_entry(title, link, summary, updated="2026-06-05T12:00:00Z",
                author_name="A. N. Author"):
    return f"""<entry>
<title>{title}</title>
<link href="{link}"/>
<summary>{summary}</summary>
<updated>{updated}</updated>
<author><name>{author_name}</name></author>
</entry>"""


def _atom_doc(entries, feed_title="Test Atom Feed"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>{feed_title}</title>
{entries}
</feed>"""


class TestScrapeCybersec(unittest.TestCase):
    """scrape_cybersec() must iterate 3 feeds and tag each article
    with the per-feed source_key."""

    EXPECTED_FEEDS = 3

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False

    def test_three_feeds_one_article_each(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        items = _rss_item("Breach at CorpX", "https://x/1", "details")
        rss = _rss_doc(items)
        fetched_urls = []

        def fake_fetch(url, **kw):
            fetched_urls.append(url)
            return rss

        with patch.object(self.news_tool, "fetch_url", side_effect=fake_fetch):
            articles = self.news_tool.scrape_cybersec()

        self.assertEqual(len(articles), 3,
                         f"expected 3 articles (1 per feed × 3 feeds), got {len(articles)}")
        self.assertEqual(len(fetched_urls), 3,
                         f"expected 3 feed fetches, got {len(fetched_urls)}")
        for a in articles:
            self.assertIn(a["source_key"],
                          ("thehackersnews", "bleepingcomputer", "KrebsOnSecurity"))

    def test_failed_fetch_skips_feed(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url", return_value=""):
            articles = self.news_tool.scrape_cybersec()
        self.assertEqual(articles, [])

    def test_malformed_rss_does_not_crash(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url", return_value="not valid xml"):
            articles = self.news_tool.scrape_cybersec()
        self.assertEqual(articles, [])


class TestScrapeTech(unittest.TestCase):
    """scrape_tech() must iterate 3 feeds (TechCrunch, The Verge,
    Ars Technica) and tag each article with its source_key."""

    EXPECTED_FEEDS = 3

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False

    def test_three_feeds_articles_have_source_keys(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        items = _rss_item("Tech headline", "https://t/1", "tech details")
        rss = _rss_doc(items)
        fetched_urls = []

        def fake_fetch(url, **kw):
            fetched_urls.append(url)
            return rss

        with patch.object(self.news_tool, "fetch_url", side_effect=fake_fetch):
            articles = self.news_tool.scrape_tech()

        self.assertEqual(len(articles), 3)
        self.assertEqual(len(fetched_urls), 3)
        for a in articles:
            self.assertIn(a["source_key"], ("techcrunch", "theverge", "arstechnica"))

    def test_atom_format_supported(self):
        """Some feeds (e.g. The Verge) return Atom <entry> not RSS <item>.
        parse_rss() must fall back to <entry> regex when <item> yields
        nothing."""
        if not self._requests_available:
            self.skipTest("requests not available")
        atom = _atom_doc(_atom_entry("Atom article", "https://t/a", "atom summary"))

        def fake_fetch(url, **kw):
            if "theverge" in url:
                return atom
            return ""

        with patch.object(self.news_tool, "fetch_url", side_effect=fake_fetch):
            articles = self.news_tool.scrape_tech()
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "Atom article")
        self.assertEqual(articles[0]["source_key"], "theverge")


class TestScrapeGoogleNews(unittest.TestCase):
    """scrape_google_news() must hit 3 query feeds, parse them, and
    resolve any news.google.com/articles/ redirect URLs."""

    GN_REDIRECT_RSS = _rss_doc(_rss_item(
        "AI news item",
        "https://news.google.com/articles/CAIiEFAKE_REDIRECT_TOKEN",
        "AI summary",
    ))

    GN_CANONICAL_RSS = _rss_doc(_rss_item(
        "Real article",
        "https://www.reuters.com/real-article",
        "summary",
    ))

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False

    def test_three_queries_four_articles_each(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url",
                          return_value=self.GN_CANONICAL_RSS), \
             patch.object(self.news_tool, "resolve_google_news_redirect",
                          side_effect=lambda u: u):
            articles = self.news_tool.scrape_google_news()
        # 1 article × 3 queries = 3
        self.assertEqual(len(articles), 3)
        for a in articles:
            self.assertEqual(a["source_key"], "google-news")

    def test_google_news_redirect_url_is_resolved(self):
        """Articles with news.google.com/articles/ URLs must be passed
        through resolve_google_news_redirect before being returned."""
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url",
                          return_value=self.GN_REDIRECT_RSS), \
             patch.object(
                 self.news_tool, "resolve_google_news_redirect",
                 return_value="https://www.reuters.com/resolved-article"
             ) as resolve_mock:
            articles = self.news_tool.scrape_google_news()
        self.assertGreater(len(articles), 0)
        self.assertEqual(articles[0]["url"],
                         "https://www.reuters.com/resolved-article")
        self.assertGreater(resolve_mock.call_count, 0)

    def test_resolve_skipped_for_non_google_urls(self):
        """Articles whose URL doesn't contain 'news.google.com/articles/'
        must NOT be passed through the resolver."""
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url",
                          return_value=self.GN_CANONICAL_RSS), \
             patch.object(self.news_tool, "resolve_google_news_redirect") as resolve_mock:
            self.news_tool.scrape_google_news()
        resolve_mock.assert_not_called()


class TestScrapeMarkets(unittest.TestCase):
    """scrape_markets() must iterate 2 RSS feeds (CNBC, MarketWatch)."""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False

    def test_two_feeds_one_article_each(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        items = _rss_item("Market headline", "https://m/1", "mkt summary")
        rss = _rss_doc(items)
        fetched_urls = []

        def fake_fetch(url, **kw):
            fetched_urls.append(url)
            return rss

        with patch.object(self.news_tool, "fetch_url", side_effect=fake_fetch):
            articles = self.news_tool.scrape_markets()
        self.assertEqual(len(articles), 2)
        self.assertEqual(len(fetched_urls), 2)
        for a in articles:
            self.assertIn(a["source_key"], ("CNBC", "MarketWatch"))

    def test_failed_fetch_returns_empty(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url", return_value=""):
            articles = self.news_tool.scrape_markets()
        self.assertEqual(articles, [])


class TestParseRssEdgeCases(unittest.TestCase):
    """parse_rss() edge cases that don't fit a specific scraper test."""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool

    def test_atom_entry_fallback(self):
        """When <item> matches nothing, parse_rss() must fall back to
        the Atom <entry> regex and parse the same fields."""
        atom = _atom_doc(_atom_entry(
            "Atom title", "https://a/1", "Atom summary",
            updated="2026-06-05T12:00:00Z",
            author_name="A. Author",
        ))
        articles = self.news_tool.parse_rss(atom, "atom-source")
        self.assertEqual(len(articles), 1)
        a = articles[0]
        self.assertEqual(a["title"], "Atom title")
        self.assertEqual(a["url"], "https://a/1")
        self.assertIn("Atom summary", a["summary"])
        self.assertEqual(a["source_key"], "atom-source")

    def test_html_entities_unescaped_in_atom(self):
        atom = _atom_doc(_atom_entry(
            "Q&amp;A &lt;retrieval&gt;", "https://a/2", "test &quot;x&quot;",
        ))
        articles = self.news_tool.parse_rss(atom, "atom")
        self.assertEqual(articles[0]["title"], 'Q&A <retrieval>')
        self.assertIn('"x"', articles[0]["summary"])

    def test_empty_rss_returns_empty(self):
        articles = self.news_tool.parse_rss(
            '<?xml version="1.0"?><rss><channel><title>x</title></channel></rss>',
            "x",
        )
        self.assertEqual(articles, [])

    def test_source_name_lookup(self):
        """The 'source' field must be the human-readable name from
        SOURCE_NAMES, not the raw source_key."""
        items = _rss_item("Title", "https://x/1", "summary")
        rss = _rss_doc(items)
        articles = self.news_tool.parse_rss(rss, "arxiv")
        self.assertEqual(articles[0]["source"], "arXiv",
                         f"expected 'arXiv' from SOURCE_NAMES, got {articles[0]['source']!r}")


class TestResolveGoogleNewsRedirect(unittest.TestCase):
    """resolve_google_news_redirect() is a no-op for non-Google URLs
    and tries HEAD/GET resolution for news.google.com/articles/ URLs."""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool

    def test_non_google_url_passthrough(self):
        """URLs without 'news.google.com/articles/' must be returned
        unchanged with no network call."""
        url = "https://www.reuters.com/article/x"
        with patch.object(self.news_tool.urllib.request, "urlopen") as urlopen_mock:
            result = self.news_tool.resolve_google_news_redirect(url)
        self.assertEqual(result, url)
        urlopen_mock.assert_not_called()

    def test_google_url_returns_original_on_failure(self):
        """If both HEAD and GET fail to resolve, the function must
        return the original URL (never raise)."""
        url = "https://news.google.com/articles/CAIiE_FAKE"
        with patch.object(self.news_tool.urllib.request, "urlopen",
                          side_effect=OSError("network down")):
            with patch.object(self.news_tool, "fetch_url", return_value=""):
                result = self.news_tool.resolve_google_news_redirect(url)
        self.assertEqual(result, url, "on resolution failure, return original URL")


if __name__ == "__main__":
    unittest.main()
