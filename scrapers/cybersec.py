"""Cybersecurity scraper: 3 RSS feeds (Hackers News, BleepingComputer, Krebs)."""
from ._http import fetch_url, ArticleList
from ._rss import parse_rss


def scrape_cybersec() -> ArticleList:
    print("  [4/8] Cybersecurity feeds...")
    feeds = [
        ("https://feeds.feedburner.com/TheHackersNews", "thehackersnews"),
        ("https://www.bleepingcomputer.com/feed/", "bleepingcomputer"),
        ("https://krebsonsecurity.com/feed/", "KrebsOnSecurity"),
    ]
    articles: ArticleList = []
    for url, key in feeds:
        content = fetch_url(url)
        if content:
            articles.extend(parse_rss(content, key))
    print(f"    Found {len(articles)} articles")
    return articles
