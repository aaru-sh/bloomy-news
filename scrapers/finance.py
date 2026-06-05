"""Finance scraper: Finnhub (JSON) + Yahoo Finance / Investing.com (RSS)."""
from datetime import datetime

from config import get_finnhub_key

from ._http import fetch_url, fetch_json, ArticleList
from ._rss import parse_rss


def scrape_finance() -> ArticleList:
    print("  [5/8] Finance news...")
    api_key = get_finnhub_key()

    articles: ArticleList = []

    if api_key and not api_key.startswith("YOUR_"):
        url = f"https://finnhub.io/api/v1/news?category=general&token={api_key}"
        data = fetch_json(url)
        if data:
            for item in data[:15]:
                articles.append({
                    "title": item.get("headline", ""),
                    "url": item.get("url", ""),
                    "summary": item.get("summary", "") or "",
                    "source": "Finnhub",
                    "source_key": "finnhub",
                    "published": datetime.fromtimestamp(item.get("datetime", 0)).isoformat(),
                })

    rss_feeds = [
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US", "YahooFinance"),
        ("https://www.investing.com/rss/news.rss", "Investing.com"),
    ]
    for url, key in rss_feeds:
        content = fetch_url(url)
        if content:
            articles.extend(parse_rss(content, key))

    print(f"    Found {len(articles)} articles")
    return articles
