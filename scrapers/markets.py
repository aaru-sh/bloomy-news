"""Markets scraper: 2 RSS feeds (CNBC, MarketWatch)."""
from ._http import fetch_url, ArticleList
from ._rss import parse_rss


def scrape_markets() -> ArticleList:
    print("  [8/8] Market data...")
    feeds = [
        ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC"),
        ("https://feeds.marketwatch.com/marketwatch/topstories/", "MarketWatch"),
    ]
    articles: ArticleList = []
    for url, key in feeds:
        content = fetch_url(url)
        if content:
            articles.extend(parse_rss(content, key))
    print(f"    Found {len(articles)} articles")
    return articles
