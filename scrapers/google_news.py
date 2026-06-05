"""Google News AI/ML scraper: 3 RSS queries with redirect URL resolution."""
import re
import urllib.request

from ._http import fetch_url, ArticleList
from ._rss import parse_rss


def resolve_google_news_redirect(url: str, timeout: int = 10) -> str:
    """Resolve a Google News redirect URL to the actual article URL.

    Google News RSS emits URLs like
        https://news.google.com/articles/CAIiE...
        https://news.google.com/rss/articles/CAIiE...
    These are click-tracking redirects that bounce through several
    Google properties before landing on the real publisher. Storing
    the redirect URL means users click a Google tracker instead of
    the article.

    For non-Google URLs this is a no-op (cheap string check first,
    no network call). For Google News URLs we try HEAD with redirect
    following; if that doesn't escape the news.google.com domain
    (which it usually doesn't, because Google renders a JS page),
    we fall back to a GET and look for <link rel="canonical"> or
    <meta property="og:url">. Returns the original URL on any
    failure so we never break the pipeline.
    """
    if 'news.google.com/articles/' not in url:
        return url
    try:
        req = urllib.request.Request(url, method='HEAD', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = resp.url
            if final and final != url and 'news.google.com' not in final:
                return final
    except Exception:
        pass
    try:
        content = fetch_url(url, timeout=timeout, retries=1)
        if content:
            canonical = re.search(r'<link rel="canonical" href="([^"]+)"', content)
            if canonical:
                return canonical.group(1)
            og = re.search(r'<meta property="og:url" content="([^"]+)"', content)
            if og:
                return og.group(1)
    except Exception:
        pass
    return url


def scrape_google_news() -> ArticleList:
    print("  [7/8] Google News AI/ML...")
    queries = [
        "artificial+intelligence+machine+learning",
        "cybersecurity+news",
        "stock+market+trading",
    ]
    articles: ArticleList = []
    for q in queries:
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        content = fetch_url(url)
        if content:
            arts = parse_rss(content, "google-news")
            for a in arts:
                if 'news.google.com/articles/' in a.get('url', ''):
                    a['url'] = resolve_google_news_redirect(a['url'])
            articles.extend(arts)
    print(f"    Found {len(articles)} articles")
    return articles
