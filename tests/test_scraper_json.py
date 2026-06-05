"""Scraper correctness tests for the JSON and HTML scrapers in
news_tool.py. Covers:

  - scrape_github()   (HTML scraping of GitHub trending)
  - scrape_newsapi()  (NewsAPI JSON)
  - scrape_finance()  (Finnhub JSON + 2 RSS feeds)

The remaining RSS-only scrapers (cybersec, tech, google_news, markets)
and `parse_rss()` edge cases are covered in tests/test_scraper_rss.py.

All tests use unittest.mock.patch on news_tool.fetch_url / fetch_json
to avoid real HTTP calls. They lock in CURRENT behavior so a future
feedparser or refactor is verifiable by re-running the same tests.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "dashboard"))


class TestScrapeGithub(unittest.TestCase):
    """scrape_github() must parse GitHub trending HTML for 3 languages
    and return up to 10 repos per language tagged as source_key='github'."""

    GH_HTML = """<html><body>
<article>
<h2><a href="/owner1/repo1" data-view-component="true">owner1 / repo1</a></h2>
<p class="col-9 my-1 text-small text-gray">A fast Python web framework</p>
</article>
<article>
<h2><a href="/owner2/repo2">owner2 / repo2</a></h2>
<p class="col-9 my-1 text-small text-gray">CLI tool for data science</p>
</article>
<article>
<h2><a href="/owner3/repo3">owner3 / repo3</a></h2>
<p class="col-9 my-1 text-small text-gray">Some Rust crate</p>
</article>
</body></html>"""

    GH_HTML_NO_DESC = """<html><body>
<article>
<h2><a href="/owner1/repo1">owner1 / repo1</a></h2>
</article>
</body></html>"""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False

    def test_parses_three_repos_per_language(self):
        """scrape_github() iterates 3 languages. With 3 repos in the
        canned HTML, the function returns 3 repos × 3 languages = 9."""
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url", return_value=self.GH_HTML):
            articles = self.news_tool.scrape_github()
        self.assertEqual(len(articles), 9,
                         f"expected 3 repos × 3 langs = 9, got {len(articles)}")
        self.assertEqual(articles[0]["title"], "owner1/repo1")
        self.assertEqual(articles[0]["url"], "https://github.com/owner1/repo1")
        self.assertEqual(articles[0]["source"], "GitHub")
        self.assertEqual(articles[0]["source_key"], "github")
        self.assertIn("Python web framework", articles[0]["summary"])

    def test_missing_description_gets_default(self):
        """An article with no <p class='col-9...'> description must get
        a fallback 'Trending <lang> repository on GitHub' summary."""
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url", return_value=self.GH_HTML_NO_DESC):
            articles = self.news_tool.scrape_github()
        # 1 repo × 3 langs = 3
        self.assertEqual(len(articles), 3)
        for a in articles:
            self.assertIn("Trending", a["summary"])
            self.assertIn("repository on GitHub", a["summary"])

    def test_empty_html_returns_empty(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url", return_value=""):
            articles = self.news_tool.scrape_github()
        self.assertEqual(articles, [])

    def test_published_is_iso_now(self):
        """GitHub articles get published=datetime.now().isoformat() since
        GitHub trending has no machine-readable date per repo."""
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_url", return_value=self.GH_HTML):
            articles = self.news_tool.scrape_github()
        self.assertTrue(all(a["published"].startswith("20") for a in articles),
                        f"expected ISO date, got {articles[0]['published']!r}")


class TestScrapeNewsapi(unittest.TestCase):
    """scrape_newsapi() must read the API key from config, hit 3
    category endpoints, and return articles from the 'articles' list."""

    NEWSAPI_OK = {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "title": "AI breakthrough announced",
                "url": "https://example.com/ai-1",
                "description": "A new model beats benchmarks",
                "publishedAt": "2026-06-05T10:00:00Z",
                "source": {"name": "TechCrunch", "id": "techcrunch"},
            },
            {
                "title": "Quantum chip unveiled",
                "url": "https://example.com/quantum-1",
                "description": "",
                "publishedAt": "2026-06-05T09:00:00Z",
                "source": {"name": "Wired"},
            },
        ],
    }

    NEWSAPI_ERROR = {"status": "error", "code": "apiKeyInvalid", "message": "bad key"}

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False
        self._env = patch.dict(os.environ, {"NEWS_API_KEY": "test_key_12345"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_skips_when_key_unset(self):
        """No NEWS_API_KEY env var must short-circuit the function
        (return []) without making any HTTP calls."""
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEWS_API_KEY", None)
            fetch_called = []
            with patch.object(self.news_tool, "fetch_json",
                              side_effect=lambda *a, **kw: (fetch_called.append(1), None)[1]):
                articles = self.news_tool.scrape_newsapi()
        self.assertEqual(articles, [])
        self.assertEqual(fetch_called, [],
                         "must not call fetch_json when API key is missing")

    def test_parses_articles_from_three_categories(self):
        """3 categories x 2 articles = 6 total, capped at 10 per cat."""
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_json", return_value=self.NEWSAPI_OK):
            articles = self.news_tool.scrape_newsapi()
        self.assertEqual(len(articles), 6)
        self.assertEqual(articles[0]["title"], "AI breakthrough announced")
        self.assertEqual(articles[0]["source"], "TechCrunch")
        self.assertEqual(articles[0]["source_key"], "newsapi")
        self.assertEqual(articles[0]["published"], "2026-06-05T10:00:00Z")
        # Empty description in source becomes empty string (not None)
        self.assertEqual(articles[1]["summary"], "")

    def test_error_status_returns_empty(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_json", return_value=self.NEWSAPI_ERROR):
            articles = self.news_tool.scrape_newsapi()
        self.assertEqual(articles, [],
                         "status:error response must not produce articles")

    def test_falsy_response_returns_empty(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_json", return_value=None):
            articles = self.news_tool.scrape_newsapi()
        self.assertEqual(articles, [])


class TestScrapeFinance(unittest.TestCase):
    """scrape_finance() must read Finnhub JSON for 15 articles plus
    2 RSS feeds. We mock fetch_json for Finnhub and fetch_url for the
    RSS feeds."""

    FINNHUB_OK = [
        {
            "headline": "Markets rally on Fed pivot",
            "url": "https://finnhub.io/news/1",
            "summary": "Stocks gained on dovish signals",
            "datetime": 1749067200,  # 2025-06-04T12:00:00Z approx
            "source": "Reuters",
        },
        {
            "headline": "Earnings season opens",
            "url": "https://finnhub.io/news/2",
            "summary": "",
            "datetime": 1749067300,
            "source": "Bloomberg",
        },
    ]

    YAHOO_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Yahoo Finance</title>
<item>
<title>S&amp;P 500 hits new high</title>
<link>https://finance.yahoo.com/news/sp500</link>
<description>Index closed up 1.2%</description>
<pubDate>Mon, 05 Jun 2026 12:00:00 GMT</pubDate>
</item>
</channel></rss>"""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False
        self._env = patch.dict(os.environ, {"FINNHUB_API_KEY": "test_finnhub_12345"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_finnhub_json_parsed_to_articles(self):
        """When Finnhub key is set, 2 items must be converted to articles
        with the right field mapping and epoch->iso datetime conversion."""
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_json", return_value=self.FINNHUB_OK), \
             patch.object(self.news_tool, "fetch_url", return_value=""):
            articles = self.news_tool.scrape_finance()
        self.assertGreaterEqual(len(articles), 2)
        a = articles[0]
        self.assertEqual(a["title"], "Markets rally on Fed pivot")
        self.assertEqual(a["source"], "Finnhub")
        self.assertEqual(a["source_key"], "finnhub")
        self.assertTrue(a["published"].startswith("20"),
                        f"expected ISO date, got {a['published']!r}")
        self.assertIn("dovish signals", a["summary"])

    def test_no_finnhub_key_still_runs_rss(self):
        """If Finnhub key is missing, the function must still process
        the 2 RSS feeds (Yahoo Finance + Investing.com)."""
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FINNHUB_API_KEY", None)
            with patch.object(self.news_tool, "fetch_json", return_value=None), \
                 patch.object(self.news_tool, "fetch_url", return_value=self.YAHOO_RSS):
                articles = self.news_tool.scrape_finance()
        self.assertGreaterEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "S&P 500 hits new high")

    def test_empty_finnhub_response_does_not_crash(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        with patch.object(self.news_tool, "fetch_json", return_value=[]), \
             patch.object(self.news_tool, "fetch_url", return_value=""):
            articles = self.news_tool.scrape_finance()
        self.assertEqual(articles, [])

    def test_finnhub_datetime_zero_does_not_crash(self):
        """datetime=0 must not crash datetime.fromtimestamp."""
        if not self._requests_available:
            self.skipTest("requests not available")
        zero_dt = [{"headline": "Zero time", "url": "https://x/0", "summary": "",
                    "datetime": 0, "source": "x"}]
        with patch.object(self.news_tool, "fetch_json", return_value=zero_dt), \
             patch.object(self.news_tool, "fetch_url", return_value=""):
            articles = self.news_tool.scrape_finance()
        self.assertEqual(len(articles), 1)
        self.assertTrue(articles[0]["published"].startswith("1970"),
                        f"epoch 0 must be 1970-01-01, got {articles[0]['published']!r}")


if __name__ == "__main__":
    unittest.main()
