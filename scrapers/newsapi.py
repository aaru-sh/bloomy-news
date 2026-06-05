"""NewsAPI scraper: top-headlines for technology/science/business."""
from config import get_newsapi_key

from ._http import fetch_json, ArticleList


def scrape_newsapi() -> ArticleList:
    print("  [3/8] NewsAPI...")
    api_key = get_newsapi_key()

    if not api_key or api_key.startswith("YOUR_"):
        print("    Skipped - no API key")
        return []

    articles: ArticleList = []
    for cat in ["technology", "science", "business"]:
        url = f"https://newsapi.org/v2/top-headlines?country=us&category={cat}&pageSize=15&apiKey={api_key}"
        data = fetch_json(url)
        if data and data.get("status") == "ok":
            for item in data.get("articles", [])[:10]:
                articles.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "summary": item.get("description", "") or "",
                    "source": item.get("source", {}).get("name", "NewsAPI"),
                    "source_key": "newsapi",
                    "published": item.get("publishedAt", ""),
                })
    print(f"    Found {len(articles)} articles")
    return articles
