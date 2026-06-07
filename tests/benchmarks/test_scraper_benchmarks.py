"""Benchmark tests for RSS/HTML parsing in each scraper.

These benchmarks measure the raw parsing throughput of each scraper's
core logic (HTML/feed parsing, not network I/O). All network calls
are mocked so the benchmarks isolate pure CPU work.

Run with: python -m pytest tests/benchmarks/test_scraper_benchmarks.py --benchmark-only
"""
import pytest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scrapers._rss import parse_rss, _parse_rss_regex
from scrapers.github import scrape_github

# ---------------------------------------------------------------------------
# Fixture: realistic RSS XML that exercise all parsing paths
# ---------------------------------------------------------------------------
RSS_FEED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>A test feed</description>
    <item>
        <title>First Article: AI Breakthrough</title>
        <link>https://example.com/article-1</link>
        <description>Summary of the first article about machine learning.</description>
        <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
        <dc:creator>Author One</dc:creator>
    </item>
    <item>
        <title>&lt;Second&gt; Article: &amp; Security</title>
        <link>https://example.com/article-2?foo=bar</link>
        <description>Summary with &lt;HTML&gt; &amp; entities &quot;inside&quot;.</description>
        <pubDate>Tue, 02 Jan 2024 13:00:00 GMT</pubDate>
    </item>
    <item>
        <title>Third Article: Finance Update</title>
        <link>https://example.com/article-3</link>
        <description>Quarterly earnings report for major tech company.</description>
        <pubDate>Wed, 03 Jan 2024 14:00:00 GMT</pubDate>
        <dc:creator>Author Three</dc:creator>
    </item>
</channel>
</rss>"""

ATOM_FEED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <title>Test Atom Feed</title>
    <entry>
        <title>Atom Entry One</title>
        <link href="https://example.com/atom-1"/>
        <summary>Atom summary for entry one.</summary>
        <published>2024-01-01T12:00:00Z</published>
        <author><name>Atom Author</name></author>
    </entry>
    <entry>
        <title>Atom Entry Two</title>
        <link href="https://example.com/atom-2"/>
        <summary>Atom summary for entry two about cybersecurity vulnerabilities.</summary>
        <updated>2024-01-02T12:00:00Z</updated>
    </entry>
</feed>"""

GITHUB_TRENDING_HTML = """\
<html><body>
<article>
<h2 class="h3 lh-condensed">
    <a href="/user/repo-alpha">user / repo-alpha</a>
</h2>
<p class="col-9 color-fg-muted my-1 pr-4">A Python library for data processing</p>
</article>
<article>
<h2 class="h3 lh-condensed">
    <a href="/user/repo-beta">user / repo-beta</a>
</h2>
<p class="col-9 color-fg-muted my-1 pr-4">Rust-based CLI tool for web scraping</p>
</article>
<article>
<h2 class="h3 lh-condensed">
    <a href="/user/repo-gamma">user / repo-gamma</a>
</h2>
<p class="col-9 color-fg-muted my-1 pr-4">Machine learning framework with GPU support</p>
</article>
</body></html>"""


# ---------------------------------------------------------------------------
# RSS parsing benchmarks
# ---------------------------------------------------------------------------
class TestRSSParserBenchmarks:
    """Benchmarks for the RSS/Atom feedparser path."""

    def test_parse_rss_xml(self, benchmark):
        """Benchmark parsing a standard RSS 2.0 XML feed."""
        result = benchmark(parse_rss, RSS_FEED_XML, "techcrunch")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all("title" in a and "url" in a for a in result)

    def test_parse_rss_atom(self, benchmark):
        """Benchmark parsing an Atom feed."""
        result = benchmark(parse_rss, ATOM_FEED_XML, "arxiv")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_parse_rss_regex_fallback(self, benchmark):
        """Benchmark the regex-based RSS parser (legacy fallback)."""
        result = benchmark(_parse_rss_regex, RSS_FEED_XML, "techcrunch")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_parse_rss_regex_atom_fallback(self, benchmark):
        """Benchmark the regex-based Atom parser (legacy fallback)."""
        result = benchmark(_parse_rss_regex, ATOM_FEED_XML, "arxiv")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_parse_rss_large_feed(self, benchmark):
        """Benchmark parsing a feed with 20 items (the per-feed cap)."""
        items = []
        for i in range(20):
            items.append(f"""\
    <item>
        <title>Article {i}: Title about topic {i}</title>
        <link>https://example.com/article-{i}</link>
        <description>Summary for article number {i} with some content.</description>
        <pubDate>Mon, 01 Jan 2024 12:00:{i:02d} GMT</pubDate>
    </item>""")
        large_feed = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>Large Feed</title>
    <link>https://example.com</link>
    <description>Feed with 20 items</description>
    {"".join(items)}
</channel>
</rss>"""
        result = benchmark(parse_rss, large_feed, "techcrunch")
        assert isinstance(result, list)
        assert len(result) == 20


# ---------------------------------------------------------------------------
# GitHub HTML parsing benchmark
# ---------------------------------------------------------------------------
class TestGitHubParserBenchmarks:
    """Benchmarks for GitHub trending page HTML parsing."""

    @patch("scrapers.github.fetch_url")
    def test_parse_github_trending(self, mock_fetch, benchmark):
        """Benchmark parsing GitHub trending HTML for all languages."""
        mock_fetch.return_value = GITHUB_TRENDING_HTML

        def run():
            from scrapers.github import scrape_github
            return scrape_github()

        result = benchmark(run)
        assert isinstance(result, list)
