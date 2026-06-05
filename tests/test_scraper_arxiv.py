"""Scraper correctness tests for the arXiv RSS scraper.

Covers `news_tool.parse_rss()` (the regex-based RSS parser used by
scrape_arxiv, scrape_cybersec, scrape_tech, scrape_google_news) and the
scrape_arxiv() driver's feed list + per-article subcategory tagging.

These tests use unittest.mock.patch on news_tool.fetch_url to avoid
real HTTP. They lock in the CURRENT behavior so a future feedparser
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


ARXIV_RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>{title}</title>
<description>arXiv {category} feed</description>
<link>https://arxiv.org/list/{category}/recent</link>
{items}
</channel>
</rss>"""


def _arxiv_item(arxiv_id, title, summary, author="Doe, J."):
    """Build a single arXiv RSS <item> matching real arXiv output shape.

    NOTE: real arXiv uses <dc:creator> for the author field, but the
    current parse_rss() helper only reads <author>. This is a known
    limitation; the test uses <author> to verify the parser's happy
    path, and a separate test exercises the dc:creator gap.
    """
    return f"""<item>
<title>{title}</title>
<link>https://arxiv.org/abs/{arxiv_id}</link>
<description>{summary}</description>
<author>{author}</author>
<pubDate>Mon, 05 Jun 2026 12:00:00 GMT</pubDate>
<guid isPermaLink="false">oai:arXiv.org:{arxiv_id}</guid>
</item>"""


class TestArxivParseRss(unittest.TestCase):
    """parse_rss() must extract title, link, summary, pubDate, author
    from canonical arXiv-shaped RSS, and tag each article with the
    supplied source_key."""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool

    def test_single_item_extracted(self):
        xml = ARXIV_RSS_TEMPLATE.format(
            title="cs.AI",
            category="cs.AI",
            items=_arxiv_item(
                "2606.12345",
                "A new transformer architecture for reasoning",
                "We propose a novel attention mechanism.",
            ),
        )
        articles = self.news_tool.parse_rss(xml, "arxiv")
        self.assertEqual(len(articles), 1)
        a = articles[0]
        self.assertEqual(a["title"], "A new transformer architecture for reasoning")
        self.assertEqual(a["url"], "https://arxiv.org/abs/2606.12345")
        self.assertIn("novel attention", a["summary"])
        self.assertEqual(a["author"], "Doe, J.")
        self.assertEqual(a["published"], "Mon, 05 Jun 2026 12:00:00 GMT")
        self.assertEqual(a["source_key"], "arxiv")
        self.assertEqual(a["source"], "arXiv")

    def test_multiple_items_all_extracted(self):
        items = "\n".join([
            _arxiv_item("2606.00001", "Paper one", "Summary one"),
            _arxiv_item("2606.00002", "Paper two", "Summary two"),
            _arxiv_item("2606.00003", "Paper three", "Summary three"),
        ])
        xml = ARXIV_RSS_TEMPLATE.format(title="cs.AI", category="cs.AI", items=items)
        articles = self.news_tool.parse_rss(xml, "arxiv")
        self.assertEqual(len(articles), 3)
        self.assertEqual([a["url"].rsplit("/", 1)[-1] for a in articles],
                         ["2606.00001", "2606.00002", "2606.00003"])

    def test_cdata_wrapping_stripped(self):
        xml = ARXIV_RSS_TEMPLATE.format(
            title="cs.AI",
            category="cs.AI",
            items=f"""<item>
<title><![CDATA[CDATA-wrapped title]]></title>
<link>https://arxiv.org/abs/2606.99999</link>
<description><![CDATA[CDATA-wrapped <em>summary</em>]]></description>
<pubDate>Mon, 05 Jun 2026 12:00:00 GMT</pubDate>
</item>""",
        )
        articles = self.news_tool.parse_rss(xml, "arxiv")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "CDATA-wrapped title")
        self.assertIn("CDATA-wrapped", articles[0]["summary"])
        self.assertNotIn("<em>", articles[0]["summary"],
                         "inline HTML in summary must be stripped")

    def test_html_entities_unescaped(self):
        xml = ARXIV_RSS_TEMPLATE.format(
            title="cs.AI",
            category="cs.AI",
            items="""<item>
<title>Q&amp;A: a survey of &lt;retrieval&gt; methods</title>
<link>https://arxiv.org/abs/2606.11111</link>
<description>Survey covers &quot;modern&quot; techniques.</description>
<pubDate>Mon, 05 Jun 2026 12:00:00 GMT</pubDate>
</item>""",
        )
        articles = self.news_tool.parse_rss(xml, "arxiv")
        self.assertEqual(articles[0]["title"], 'Q&A: a survey of <retrieval> methods')
        self.assertIn('"modern"', articles[0]["summary"])

    def test_summary_truncated_to_600_chars(self):
        long_summary = "x" * 1000
        xml = ARXIV_RSS_TEMPLATE.format(
            title="cs.AI",
            category="cs.AI",
            items=_arxiv_item("2606.22222", "Long summary paper", long_summary),
        )
        articles = self.news_tool.parse_rss(xml, "arxiv")
        self.assertLessEqual(len(articles[0]["summary"]), 600)

    def test_item_missing_required_fields_rejected(self):
        """An item with no <link> and no <title> must be dropped, not
        included as an empty article."""
        xml = ARXIV_RSS_TEMPLATE.format(
            title="cs.AI",
            category="cs.AI",
            items="""<item>
<description>no title, no link</description>
</item>""",
        )
        articles = self.news_tool.parse_rss(xml, "arxiv")
        self.assertEqual(articles, [],
                         "item with empty title and empty url must be dropped")

    def test_dc_creator_captured(self):
        """Real arXiv uses <dc:creator>. feedparser maps this to
        entry.author; the v1.2.0 swap fixes what was a regex-parser
        limitation."""
        xml = ARXIV_RSS_TEMPLATE.format(
            title="cs.AI",
            category="cs.AI",
            items="""<item>
<title>dc:creator-only item</title>
<link>https://arxiv.org/abs/2606.33333</link>
<description>summary</description>
<dc:creator>Real Author</dc:creator>
<pubDate>Mon, 05 Jun 2026 12:00:00 GMT</pubDate>
</item>""",
        )
        articles = self.news_tool.parse_rss(xml, "arxiv")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["author"], "Real Author",
                         "feedparser must capture <dc:creator> as author")


class TestScrapeArxivFeedList(unittest.TestCase):
    """scrape_arxiv() must iterate over all 13 configured feed categories
    and tag each returned article with its subcategory."""

    EXPECTED_CATEGORIES = [
        "cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE", "cs.RO",
        "cs.IR", "cs.MA", "cs.HC", "stat.ML", "eess.SP",
        "q-fin.ST", "cs.CR",
    ]

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False
        self._env = patch.dict(os.environ, {"ARXIV_RATE_LIMIT": "0.0"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_feed_list_has_13_categories(self):
        if not self._requests_available:
            self.skipTest("requests not available")
        seen_urls = []
        with patch.object(self.news_tool, "fetch_url",
                          side_effect=lambda url, **kw: (seen_urls.append(url), "")[1]):
            self.news_tool.scrape_arxiv()
        self.assertEqual(len(seen_urls), 13,
                         f"expected 13 feed fetches, got {len(seen_urls)}")
        for cat in self.EXPECTED_CATEGORIES:
            self.assertIn(f"rss/{cat}", "\n".join(seen_urls),
                          f"feed for {cat} not in fetch list")

    def test_per_article_subcategory_set_from_feed(self):
        if not self._requests_available:
            self.skipTest("requests not available")

        def fake_fetch(url, **kw):
            cat = url.rsplit("/", 1)[-1]
            return ARXIV_RSS_TEMPLATE.format(
                title=cat,
                category=cat,
                items=_arxiv_item("2606.00001", f"Paper in {cat}", "summary"),
            )

        with patch.object(self.news_tool, "fetch_url", side_effect=fake_fetch):
            articles = self.news_tool.scrape_arxiv()

        self.assertEqual(len(articles), 13)
        subcats = sorted({a["subcategory"] for a in articles})
        self.assertEqual(subcats, sorted(self.EXPECTED_CATEGORIES))

    def test_failed_fetch_skips_category(self):
        """A fetch that returns falsy (network error, empty body) must
        silently skip the category without aborting the whole loop."""
        if not self._requests_available:
            self.skipTest("requests not available")

        def fake_fetch(url, **kw):
            return ""  # simulate empty / failed response

        with patch.object(self.news_tool, "fetch_url", side_effect=fake_fetch):
            articles = self.news_tool.scrape_arxiv()
        self.assertEqual(articles, [],
                         "all-empty fetches should yield zero articles, not raise")


class TestScrapeArxivRateLimitRegression(unittest.TestCase):
    """ARXIV_RATE_LIMIT env var must be honored between feed fetches.
    Covered in detail by tests/test_fixes.py::TestArxivRateLimit; this
    is a single smoke test that the contract still holds."""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool
        try:
            import requests  # noqa: F401
            self._requests_available = True
        except ImportError:
            self._requests_available = False

    def test_zero_rate_limit_still_calls_sleep_n_times(self):
        """ARXIV_RATE_LIMIT=0.0 still calls time.sleep(0.0) between feeds.
        With 13 feeds that's 12 calls (one between each pair). The call
        is a no-op but the contract is "sleep(limit) between feeds",
        not "skip sleep when limit is 0"."""
        if not self._requests_available:
            self.skipTest("requests not available")
        sleep_calls = []
        with patch.dict(os.environ, {"ARXIV_RATE_LIMIT": "0.0"}):
            with patch.object(self.news_tool.time, "sleep",
                              side_effect=lambda s: sleep_calls.append(s)):
                with patch.object(self.news_tool, "fetch_url", return_value=""):
                    self.news_tool.scrape_arxiv()
        self.assertEqual(sleep_calls, [0.0] * 12,
                         f"expected 12 zero-duration sleeps (13 feeds - 1), "
                         f"got {sleep_calls!r}")


class TestParseRssFallbackToRegex(unittest.TestCase):
    """When feedparser raises (e.g. on pathological input that crashes
    the C extension), parse_rss() must fall back to the legacy regex
    parser instead of dropping the whole feed. This locks in the
    v1.2.0 feedparser swap's safety net."""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool

    def test_falls_back_when_feedparser_raises(self):
        valid_xml = ARXIV_RSS_TEMPLATE.format(
            title="cs.AI",
            category="cs.AI",
            items=_arxiv_item("2606.44444", "Fallback test", "summary"),
        )
        import feedparser
        call_count = [0]
        original_parse = feedparser.parse

        def boom(*a, **kw):
            call_count[0] += 1
            raise RuntimeError("simulated feedparser crash")

        feedparser.parse = boom
        try:
            articles = self.news_tool.parse_rss(valid_xml, "arxiv")
        finally:
            feedparser.parse = original_parse

        self.assertEqual(len(articles), 1,
                         "regex fallback must produce the same article")
        self.assertEqual(articles[0]["title"], "Fallback test")
        self.assertEqual(articles[0]["url"], "https://arxiv.org/abs/2606.44444")
        self.assertEqual(call_count[0], 1, "feedparser must be tried once before fallback")


class TestParseRssFeedparserPrimary(unittest.TestCase):
    """Lock in the v1.2.0 feedparser swap: parse_rss() now uses
    feedparser as the primary path (not the regex fallback)."""

    def setUp(self):
        import news_tool
        self.news_tool = news_tool

    def test_feedparser_called_for_normal_rss(self):
        """For a well-formed RSS document, feedparser.parse must be
        called (not the regex fallback)."""
        import feedparser
        valid_xml = ARXIV_RSS_TEMPLATE.format(
            title="cs.AI",
            category="cs.AI",
            items=_arxiv_item("2606.55555", "Primary path", "summary"),
        )
        call_count = [0]
        original_parse = feedparser.parse

        def counting_parse(*a, **kw):
            call_count[0] += 1
            return original_parse(*a, **kw)

        feedparser.parse = counting_parse
        try:
            self.news_tool.parse_rss(valid_xml, "arxiv")
        finally:
            feedparser.parse = original_parse
        self.assertEqual(call_count[0], 1,
                         "feedparser.parse must be called exactly once for valid RSS")

    def test_atom_entry_uses_feedparser(self):
        """Atom <feed><entry> documents must be parsed by feedparser
        (not the regex fallback) so the result uses the same shape."""
        atom = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Atom Feed</title>
<entry>
<title>Atom article</title>
<link href="https://example.com/atom-1"/>
<summary>Atom summary</summary>
<updated>2026-06-05T12:00:00Z</updated>
<author><name>A. Author</name></author>
</entry>
</feed>"""
        articles = self.news_tool.parse_rss(atom, "atom-source")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "Atom article")
        self.assertEqual(articles[0]["url"], "https://example.com/atom-1")
        self.assertEqual(articles[0]["author"], "A. Author")


if __name__ == "__main__":
    unittest.main()
