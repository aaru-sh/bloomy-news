"""Tech news scraper: 3 RSS feeds (TechCrunch, The Verge, Ars Technica)."""
from ._http import fetch_url, ArticleList
from ._rss import parse_rss


def scrape_tech() -> ArticleList:
    print("  [6/8] Tech news...")
    feeds = [
        ("https://techcrunch.com/feed/", "techcrunch"),
        ("https://www.theverge.com/rss/index.xml", "theverge"),
        ("https://arstechnica.com/feed/", "arstechnica"),
    ]
    articles: ArticleList = []
    for url, key in feeds:
        content = fetch_url(url)
        if content:
            articles.extend(parse_rss(content, key))
    print(f"    Found {len(articles)} articles")
    return articles
